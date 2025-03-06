from evaluation.executor.task_pool import *
import numpy as np
import random
import torch
import asyncio
import sys
import pickle
import grpc
from evaluation.executor.channels import executor_pb2
from evaluation.executor.channels import executor_pb2_grpc
from evaluation.internal.fllibs import init_model


class Worker_manager:
    def __init__(self, config, logger):
        """Init worker class

        Args:
            config:
        """
        self.job_id_agg_weight_map = {}
        self.job_id_agg_meta = {}
        self.job_id_agg_test_map = {}
        self.logger = logger
        self._setup_seed()
        self.config = config
        self.worker_num = len(config["worker"])
        self.worker_addr_list = config["worker"]
        self.worker_channel_dict = {}
        self.worker_stub_dict = {}
        self._connect_worker()
        self.cur_worker = 0
        self.num_task = 0

    def _connect_worker(self):
        channel_options = [
            ('grpc.max_receive_message_length', MAX_MESSAGE_LENGTH),
            ('grpc.max_send_message_length', MAX_MESSAGE_LENGTH)
        ]
        for worker_id, worker_addr in enumerate(self.worker_addr_list):
            worker_ip = worker_addr["ip"] if not self.config["use_docker"] else f"worker_{worker_id}"
            worker_port = worker_addr["port"]
            self.worker_channel_dict[worker_id] = grpc.aio.insecure_channel(f"{worker_ip}:{worker_port}", options=channel_options)
            self.worker_stub_dict[worker_id] = executor_pb2_grpc.WorkerStub(
                self.worker_channel_dict[worker_id]
            )
            self.logger.print(f"Worker manager: connecting to worker {worker_id} at {worker_ip}:{worker_port}", INFO)
    
    async def _disconnect(self):
        for worker_channel in self.worker_channel_dict.values():
            await worker_channel.close()

    def _setup_seed(self, seed=1):
        torch.manual_seed(seed)
        torch.backends.cudnn.deterministic = True
        torch.cuda.manual_seed_all(seed)
        np.random.seed(seed)
        random.seed(seed)


    async def remove_job(self, job_id: int):
        if job_id in self.job_id_agg_weight_map:
            del self.job_id_agg_weight_map[job_id]
            del self.job_id_agg_meta[job_id]
        if job_id in self.job_id_agg_test_map:
            del self.job_id_agg_test_map[job_id]
        
        job_info_msg = executor_pb2.job_info(
            job_id=job_id,
            job_meta=pickle.dumps(DUMMY_RESPONSE)
        )

        # broadcast
        for worker_stub in self.worker_stub_dict.values():
            await worker_stub.REMOVE(job_info_msg)


    async def init_job(self, job_id: int, dataset_name: str, model_name: str, args: dict)->float:
        model = init_model(model_name, dataset_name)
        model_size = sys.getsizeof(pickle.dumps(model)) / 1024.0 * 8.  # kbits
        self.logger.print(f"model: {model_name}, size: {model_size}")
        # broadcast
        
        job_init_msg = executor_pb2.job_init(
            job_id=job_id,
            job_meta=pickle.dumps(args),
            model_weight=pickle.dumps(model)
        )

        for worker_stub in self.worker_stub_dict.values():
            await worker_stub.INIT(job_init_msg)
        
        self.job_id_agg_weight_map[job_id] = None
        self.job_id_agg_meta[job_id] = {"cnt": 0, "moving_loss": 0, "trained_size": 0}
        self.job_id_agg_test_map[job_id] = {
            "cnt": 0,
            "test_loss": 0,
            "acc": 0,
            "acc_5": 0,
            "test_len": 0
        }
        
        self.logger.print(f"Worker manager: init job {job_id} success", INFO)

        return model_size
        
    async def heartbeat_routine(self):
        try:
            while True:
                await asyncio.sleep(10)
                
                status_list = []

                for worker_stub in self.worker_stub_dict.values():
                    worker_status_msg = await worker_stub.HEART_BEAT(executor_pb2.empty())
                    status_list.append(worker_status_msg.task_size)
                
                # self.cur_worker = status_list.index(min(status_list))
                self.logger.print(f"Worker manager: current worker {self.cur_worker}", PRINT)
        except asyncio.CancelledError:
            pass

    def update_agg(self, agg_weight, agg_meta: list, result_list: list, meta: dict, gradient_policy):
        for key, value in meta.items():
            # cnt, trained_size
            agg_meta[key] += value

        for result in result_list:
            agg_meta["moving_loss"] += result["moving_loss"]
            if gradient_policy != 'q-fedavg':
                model_weight = result["model_weight"]
                if not agg_weight:
                    agg_weight = model_weight
                else:
                    agg_weight = [weight + model_weight[i] for i, weight in enumerate(agg_weight)]
            else:
                Delta, h = result["Delta"], result["h"]
                if not agg_weight:
                    agg_weight = [Delta, h]
                else:
                    agg_weight[1] += h
                    for idx in range(len(Delta)):
                        agg_weight[0][idx] += Delta[idx]
        return agg_weight
        
    async def execute(self, event: str, job_id: int, client_id_list: list, round: int, args: dict)->dict:
        try:
            results = None
            if event == CLIENT_TRAIN or event == MODEL_TEST:
                task_id = self.num_task
                self.num_task += 1

                self.cur_worker = (self.cur_worker + 1) % self.worker_num
                cur_worker = self.cur_worker

                job_task_msg = executor_pb2.worker_task(
                    job_id=job_id,
                    round=round,
                    task_id=task_id,
                    client_id_list=pickle.dumps(client_id_list),
                    event=event,
                    task_meta=pickle.dumps(args),
                )

                await self.worker_stub_dict[cur_worker].TASK_REGIST(job_task_msg)
                ping_num = 0
                await asyncio.sleep(1)
                while True:
                    ping_msg = executor_pb2.worker_task_info(
                        job_id=job_id,
                        task_id=task_id,
                    )
                    task_result_msg = await self.worker_stub_dict[cur_worker].PING(ping_msg)

                    if task_result_msg.ack:
                        results = pickle.loads(task_result_msg.result_data)
                        break

                    ping_num += 1
                    if ping_num >= 30:
                        self.logger.print(f"Unable to retrieve job {job_id} task {task_id}", ERROR)
                        return None
                    await asyncio.sleep(0.5)

                if event == CLIENT_TRAIN:
                    result_list = results["result_list"]
                    del results["result_list"]
                    gradient_policy = results["gradient_policy"]
                    del results["gradient_policy"]

                    agg_weight = self.job_id_agg_weight_map[job_id]
                    agg_meta = self.job_id_agg_meta[job_id]

                    self.job_id_agg_weight_map[job_id] = \
                        self.update_agg(agg_weight, agg_meta, result_list, results, gradient_policy)
                    
                    self.job_id_agg_meta[job_id] = agg_meta 
                
                elif event == MODEL_TEST:
                    agg_test_result = self.job_id_agg_test_map[job_id]
                    for key, value in results.items():
                        agg_test_result[key] += value
                            
            elif event == AGGREGATE:
                agg_weight = self.job_id_agg_weight_map[job_id]

                if not agg_weight:
                    raise RuntimeError("Cannot aggregate None object")

                agg_meta = self.job_id_agg_meta[job_id]
                agg_meta["avg_moving_loss"] = 0
                cnt = agg_meta["cnt"]
            
                self.job_id_agg_meta[job_id] = {"cnt":0, "moving_loss": 0, "trained_size": 0}
                if cnt > 0:
                    if args["gradient_policy"] != 'q-fedavg':
                        agg_weight = [np.divide(weight, cnt) for weight in agg_weight]

                    job_weight_msg = executor_pb2.job_weight(
                        job_id = job_id,
                        job_data = pickle.dumps(agg_weight)
                    )

                    for worker_id, worker_stub in self.worker_stub_dict.items():
                        try:
                            ack_msg = await worker_stub.UPDATE(job_weight_msg)
                            if not ack_msg.ack:
                                self.logger.print(f"Update model weight to worker {worker_id} failed", ERROR)
                        except Exception as e:
                            self.logger.print(e, ERROR)

                    agg_meta["avg_moving_loss"] = agg_meta["moving_loss"] / cnt
                
                self.job_id_agg_weight_map[job_id] = None
                results = agg_meta
            
            elif event == AGGREGATE_TEST:
                agg_test = self.job_id_agg_test_map[job_id]
                cnt = agg_test["cnt"]
                test_len = agg_test["test_len"]
                agg_test["test_loss"] /= test_len if test_len > 0 else 0
                agg_test["acc"] /= cnt if cnt > 0 else 0
                agg_test["acc_5"] /= cnt if cnt > 0 else 0

                self.job_id_agg_test_map[job_id] = {
                    "cnt": 0,
                    "test_loss": 0,
                    "acc": 0,
                    "acc_5": 0,
                    "test_len": 0
                }

                results = agg_test

            elif event == ROUND_FAIL:
                self.job_id_agg_test_map[job_id] = {
                    "cnt": 0,
                    "test_loss": 0,
                    "acc": 0,
                    "acc_5": 0,
                    "test_len": 0
                }

                self.job_id_agg_meta[job_id] = {"cnt":0, "moving_loss": 0, "trained_size": 0}
                self.job_id_agg_weight_map[job_id] = None

        except Exception as e:
            self.logger.print(e, ERROR)

        return results
            

