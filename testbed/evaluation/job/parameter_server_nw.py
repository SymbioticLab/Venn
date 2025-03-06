import sys
[sys.path.append(i) for i in ['.', '..', '...']]
import asyncio
import yaml
import grpc
from propius_controller.job.propius_job_aio import Propius_job_aio
from channels import parameter_server_pb2
from channels import parameter_server_pb2_grpc
from evaluation.commons import *
from collections import deque
from evaluation.executor.channels import executor_pb2
from evaluation.executor.channels import executor_pb2_grpc
import os
import csv
import logging
import logging.handlers
import time
import pickle

_cleanup_coroutines = []

class Parameter_server(parameter_server_pb2_grpc.Parameter_serverServicer):
    def __init__(self, config):
        self.total_round = config['total_round']
        self.server = None
        self.demand = config['demand']
        self.over_demand = self.demand if "over_selection" not in config else \
            int(config["over_selection"] * config["demand"])
        
        self.do_compute = config["do_compute"]

        if config["dispatcher_use_docker"]:
            config["executor_ip"] = "executor"

        job_config = {
            "public_constraint": config["public_constraint"],
            "private_constraint": config["private_constraint"],
            "total_round": config["total_round"],
            "demand": config["demand"] if "over_selection" not in config else \
                    int(config["over_selection"] * config["demand"]),
            "job_manager_ip": config["job_manager_ip"] if not config["dispatcher_use_docker"] else "job_manager",
            "job_manager_port": config["job_manager_port"],
            "ip": config["ip"],
            "port": config["port"]
        }

        self.job_config = job_config
        self.config = config

        self.ip = config["ip"] if not config["dispatcher_use_docker"] else "0.0.0.0"
        self.port = config["port"]
        self.id = self.port

        self.lock = asyncio.Lock()
        self.cv = asyncio.Condition(self.lock)

        self.cur_round = 1
        self.client_event_dict = {} # key is client id, value is an event queue

        self.round_client_num = 0
        self.round_result_cnt = 0

        self.execution_start = False #indicating whether the scheduling phase has passed

        self.propius_stub = Propius_job_aio(job_config=job_config, verbose=True, logging=True)

        if self.do_compute:
            self.executor_ip = config['executor_ip']
            self.executor_port = config['executor_port']
            self.executor_channel = None
            self.executor_stub = None
            self._connect_to_executor()

        self.start_time = 0
        self.round_time = 0
        self.sched_time = 0
        self.response_time = 0
        self.total_sched_delay = 0
        self.total_response_time = 0
        self.num_sched_timeover = 0
        self.num_response_timeover = 0

        self.model_size = 0
        self.speedup_factor = config['speedup_factor']
        

    def _connect_to_executor(self):
        self.executor_channel = grpc.aio.insecure_channel(f"{self.executor_ip}:{self.executor_port}")
        self.executor_stub = executor_pb2_grpc.ExecutorStub(self.executor_channel)
        custom_print(f"PS: connecting to executor on {self.executor_ip}:{self.executor_port}", INFO)

    async def round_exec_start(self):
        custom_print(f"PS {self.id}-{self.cur_round}: start execution", INFO)
        await self.propius_stub.end_request()
        self.execution_start = True
        self.sched_time = time.time() - self.sched_time

    def _update_task_config(self):
        if self.cur_round % self.config["decay_round"] == 0:
            self.config["learning_rate"] = max(
                self.config["learning_rate"] * self.config["decay_factor"],
                self.config["min_learning_rate"]
            )

    def _clear_event_dict(self):
        self.client_event_dict = {}

    async def close_round(self):
        custom_print(f"PS {self.id}-{self.cur_round}: round finish", INFO)
        self._clear_event_dict()
        if self.do_compute:
            job_task_info_msg = executor_pb2.job_task_info(
                job_id=self.id,
                client_id=-1,
                round=self.cur_round,
                event=AGGREGATE,
                task_meta=pickle.dumps({
                    "gradient_policy": self.config["gradient_policy"]
                }),
            )
            await self.executor_stub.JOB_REGISTER_TASK(job_task_info_msg)
            custom_print(f"PS {self.id}-{self.cur_round}: aggregrate event reported", INFO)

        self.response_time = time.time() - self.response_time

    async def close_failed_round(self):
        self._clear_event_dict()
        if self.do_compute:
            job_task_info_msg = executor_pb2.job_task_info(
                job_id=self.id,
                client_id=-1,
                round=self.cur_round,
                event=ROUND_FAIL,
                task_meta=pickle.dumps({}),
            )
            await self.executor_stub.JOB_REGISTER_TASK(job_task_info_msg)

    async def re_register(self) -> bool:
        self.job_config['total_round'] = max(self.total_round - self.cur_round + 1, 1)
        
        custom_print(f"Parameter server: re-register, left round {self.job_config['total_round']}", WARNING)
        self.propius_stub = Propius_job_aio(job_config=self.job_config, verbose=True, logging=True)
        if not await self.propius_stub.register():    
            custom_print(f"Parameter server: re-register failed", ERROR)
            return False
        return True


    def _init_event_queue(self, client_id:int):
        event_q = deque()
        event_q.append({
            "event": UPDATE_MODEL,
            "meta": {
                "download_size": self.model_size,
                "upload_size": self.model_size,
                "round": self.cur_round
            },
            "data": {}
        })
        event_q.append({
            "event": CLIENT_TRAIN,
            "meta": {
                "batch_size": self.config["batch_size"],
                "local_steps": self.config["local_steps"],
                "gradient_policy": self.config["gradient_policy"]
            },
            "data": {}
        })
        event_q.append({
            "event": UPLOAD_MODEL,
            "meta": {
            },
            "data": {}
        })
        event_q.append({
            "event": SHUT_DOWN,
            "meta": {},
            "data": {}
        })
        self.client_event_dict[client_id] = event_q

    async def CLIENT_CHECKIN(self, request, context):
        client_id = request.id
        server_response_msg = parameter_server_pb2.server_response(
            event=SHUT_DOWN,
            meta=pickle.dumps(DUMMY_RESPONSE),
            data=pickle.dumps(DUMMY_RESPONSE)
            )

        async with self.lock:
            if not self.execution_start and \
                client_id not in self.client_event_dict \
                and self.round_client_num < self.over_demand \
                    and self.cur_round <= self.total_round:
                    
                self._init_event_queue(client_id)
                custom_print(f"PS {self.id}-{self.cur_round}: client {client_id} check-in, "
                    f"{self.round_client_num}/{self.demand}", INFO)
                
                server_response_msg = parameter_server_pb2.server_response(
                    event=DUMMY_EVENT,
                    meta=pickle.dumps(DUMMY_RESPONSE),
                    data=pickle.dumps(DUMMY_RESPONSE)
                )

                self.round_client_num += 1

                if self.round_client_num >= self.over_demand:
                    self.cv.notify()
            else:
                custom_print(f"PS {self.id}-{self.cur_round}: client {client_id} check-in rejected", WARNING)
        
            return server_response_msg
    
    async def CLIENT_PING(self, request, context):
        client_id = request.id
        server_response_msg = parameter_server_pb2.server_response(
            event=SHUT_DOWN,
            meta=pickle.dumps(DUMMY_RESPONSE),
            data=pickle.dumps(DUMMY_RESPONSE)
            )
        async with self.lock:
            if client_id in self.client_event_dict:
                event_dict = self.client_event_dict[client_id].popleft()
                server_response_msg = parameter_server_pb2.server_response(
                    event=event_dict["event"],
                    meta=pickle.dumps(event_dict["meta"]),
                    data=pickle.dumps(event_dict["data"])
                )
                custom_print(f"PS {self.id}-{self.cur_round}: client {client_id} start execute", INFO)
                    
            else:        
                # if client_id in self.client_event_dict:
                #     server_response_msg = parameter_server_pb2.server_response(
                #         event=DUMMY_EVENT,
                #         meta=pickle.dumps(DUMMY_RESPONSE),
                #         data=pickle.dumps(DUMMY_RESPONSE)
                #     )
                #     # custom_print(f"PS {self.id}-{self.cur_round}: client {client_id} ping", INFO)
                # else:
                custom_print(f"PS {self.id}-{self.cur_round}: client {client_id} ping rejected", WARNING)
            return server_response_msg

    async def CLIENT_EXECUTE_COMPLETION(self, request, context):
        client_id = request.id
        compl_event, _ = request.event, request.status
        meta, _ = pickle.loads(request.meta), pickle.loads(request.data)
        client_exec_id = meta["exec_id"]

        server_response_msg = parameter_server_pb2.server_response(
            event=SHUT_DOWN,
            meta=pickle.dumps(DUMMY_RESPONSE),
            data=pickle.dumps(DUMMY_RESPONSE)
            )
        async with self.lock:
            if meta["round"] == self.cur_round and \
                    client_id in self.client_event_dict and \
                        self.round_result_cnt <= self.demand:
                
                if compl_event == UPLOAD_MODEL:
                    custom_print(f"PS {self.id}-{self.cur_round}: client {client_id} complete, "
                                f"{self.round_result_cnt}/{self.demand}", INFO)            
                    self.round_result_cnt += 1

                    if self.do_compute:
                        local_steps = meta["local_steps"]
                        task_meta = {
                            "local_steps": local_steps,
                            "learning_rate": self.config["learning_rate"],
                            "batch_size": self.config["batch_size"],
                            "num_loaders": self.config["num_loaders"],
                            "loss_decay": self.config["loss_decay"],
                            "gradient_policy": self.config["gradient_policy"],
                            "proxy_mu": self.config["proxy_mu"] if "proxy_mu" in self.config else 0,
                            "qfed_q": self.config["qfed_q"] if "qfed_q" in self.config else 0,
                        }
                        job_task_info_msg = executor_pb2.job_task_info(
                            job_id=self.id,
                            client_id=client_exec_id,
                            round=self.cur_round,
                            event=CLIENT_TRAIN,
                            task_meta=pickle.dumps(task_meta),
                        )
                        await self.executor_stub.JOB_REGISTER_TASK(job_task_info_msg)
                        
                # Get next event
                next_event_dict = self.client_event_dict[client_id].popleft()
                if not self.client_event_dict[client_id]:
                    del self.client_event_dict[client_id]
                
                server_response_msg = parameter_server_pb2.server_response(
                    event=next_event_dict["event"],
                    meta=pickle.dumps(next_event_dict["meta"]),
                    data=pickle.dumps(next_event_dict["data"])
                )

                if self.round_result_cnt >= self.demand:
                    self.cv.notify()

            else:
                custom_print(f"PS {self.id}-{self.cur_round}: client execution rejected", WARNING)
            return server_response_msg
            
    def gen_report(self):
        csv_file_name = f"./evaluation/monitor/job/job_{self.port}_{self.config['sched_alg']}.csv"
        os.makedirs(os.path.dirname(csv_file_name), exist_ok=True)
        with open(csv_file_name, mode="a", newline="") as csv_file:
            writer = csv.writer(csv_file)
            total_round = self.cur_round
            if total_round > 0:
                writer.writerow([
                    -1,
                    -1,
                    self.total_sched_delay / (total_round + self.num_sched_timeover),
                    self.total_response_time / (total_round + self.num_response_timeover),
                ])
            writer.writerow([-2, -2, self.num_sched_timeover, self.num_response_timeover])

    async def init_report(self):
        csv_file_name = f"./evaluation/monitor/job/job_{self.port}_{self.config['sched_alg']}.csv"
        os.makedirs(os.path.dirname(csv_file_name), exist_ok=True)
        fieldnames = ["round", "round_time", "sched_delay", "response_collection_time"]
        with open(csv_file_name, "w", newline="") as csv_file:
            writer = csv.writer(csv_file)
            writer.writerow(fieldnames)

    async def gen_round_report(self):
        csv_file_name = f"./evaluation/monitor/job/job_{self.port}_{self.config['sched_alg']}.csv"
        os.makedirs(os.path.dirname(csv_file_name), exist_ok=True)

        with open(csv_file_name, mode="a", newline="") as csv_file:
            writer = csv.writer(csv_file)

            round_time = (self.round_time - self.start_time) * self.speedup_factor
            sched_delay = self.sched_time * self.speedup_factor
            response_time = self.response_time * self.speedup_factor
            self.total_sched_delay += sched_delay
            self.total_response_time += response_time
            writer.writerow([self.cur_round, 
                                round_time,
                                sched_delay,
                                response_time])
            
    async def start_server(self):
        try:
            self.server = grpc.aio.server()
            parameter_server_pb2_grpc.add_Parameter_serverServicer_to_server(self, self.server)
            self.server.add_insecure_port(f"{self.ip}:{self.port}")
            await self.server.start()
            custom_print(f"Parameter server: parameter server started, listening on {self.ip}:{self.port}", INFO)
        except Exception as e:
            custom_print(e, ERROR)
    
    async def stop_server(self, grace: float = 0):
        try:
            await self.server.stop(grace)
        except Exception as e:
            custom_print(e, ERROR)

async def run(config):
    async def server_graceful_shutdown():
        ps.gen_report()
        await ps.propius_stub.complete_job()
        
        if ps.do_compute:
            task_meta = {}
            job_task_info_msg = executor_pb2.job_task_info(
                job_id=ps.id,
                client_id=-1,
                round=ps.cur_round if ps.cur_round <= ps.total_round else ps.total_round,
                event=JOB_FINISH,
                task_meta=pickle.dumps(task_meta),
            )
            await ps.executor_stub.JOB_REGISTER_TASK(job_task_info_msg)
            await ps.executor_channel.close()
        custom_print(f"==Parameter server ending== "
                     f"sched timeout {ps.num_sched_timeover} "
                     f"response timeout {ps.num_response_timeover}", WARNING)
        
        del ps.propius_stub
        await ps.stop_server(5)
    
    ps = Parameter_server(config)
    _cleanup_coroutines.append(server_graceful_shutdown())

    # Register
    if not await ps.propius_stub.register():
        custom_print(f"Parameter server: register failed", ERROR)
        return
    
    grad_policy = config["gradient_policy"]
    job_meta = {
        "model": config["model"],
        "dataset": config["dataset"],
        "gradient_policy": grad_policy
    }
    if grad_policy == "fed-yogi":
        job_meta["yogi_eta"] = config["yogi_eta"]
        job_meta["yogi_tau"] = config["yogi_tau"]
        job_meta["yogi_beta1"] = config["yogi_beta1"]
        job_meta["yogi_beta2"] = config["yogi_beta2"]

    if ps.do_compute:
        job_info_msg = executor_pb2.job_info(job_id=ps.id, 
                                            job_meta=pickle.dumps(job_meta))
        executor_ack = await ps.executor_stub.JOB_REGISTER(job_info_msg)
        ps.model_size = executor_ack.model_size
    else:
        ps.model_size = config["model_size"] if "model_size" in config else 74016
        # for mobilenetv2 and femnist dryrun profile

    ps.start_time = time.time()
    await ps.init_report()

    await ps.start_server()
    async with ps.lock:
        while ps.cur_round <= ps.total_round:
            # if ps.cur_round % 10 == 0 or ps.num_sched_timeover % 5 == 4 or ps.num_response_timeover % 5 == 4:
            #     await ps.stop_server()
            #     await ps.start_server()

            ps.execution_start = False
            ps.round_client_num = 0
            ps.round_result_cnt = 0
            ps.sched_time = time.time()

            if not await ps.propius_stub.start_request(new_demand=False):
                if not await ps.re_register():
                    return
                await asyncio.sleep(3)
                continue
            
            try:
                timeout = config['sched_timeout'] / config['speedup_factor']
                custom_print(f"Being scheduled, wait for {timeout}", INFO)
                await asyncio.wait_for(ps.cv.wait(), timeout=timeout)
            except asyncio.TimeoutError:
                custom_print(f"PS {ps.id}-{ps.cur_round}: schedule timeout", WARNING)
                await ps.close_failed_round()
                ps.total_sched_delay += config['sched_timeout']
                ps.num_sched_timeover += 1
                continue
                
            await ps.round_exec_start()
            ps.response_time = time.time()

            try:
                timeout = config['exec_timeout'] / config['speedup_factor']
                custom_print(f"Start execute, wait for {timeout}", INFO)
                await asyncio.wait_for(ps.cv.wait(), timeout=timeout)
            except asyncio.TimeoutError:
                custom_print(f"PS {ps.id}-{ps.cur_round}: exec timeout", WARNING)
                await ps.close_failed_round()
                ps.total_response_time += config['exec_timeout']
                ps.num_response_timeover += 1
                continue

            ps.round_time = time.time()
            await ps.close_round()
            await ps.gen_round_report()
            ps.cur_round += 1
            ps._update_task_config()
            
    custom_print(
        f"Parameter server: All round finished", INFO)
    
if __name__ == '__main__':
    if len(sys.argv) != 4:
        custom_print("Usage: python evaluation/job/parameter_server/parameter_server.py <config> <ip> <port>", ERROR)
        exit(1)
        
    config_file = sys.argv[1]
    ip = sys.argv[2]
    port = int(sys.argv[3])

    log_file = f'./evaluation/monitor/job/job_{port}.log'
    os.makedirs(os.path.dirname(log_file), exist_ok=True)

    handler = logging.handlers.RotatingFileHandler(log_file, maxBytes=5000000, backupCount=5)

    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    root_logger = logging.getLogger()
    root_logger.addHandler(handler)
    root_logger.setLevel(logging.INFO)

    with open(config_file, 'r') as config:
        try:
            custom_print(f"PID: {os.getpid()}", INFO)
            config = yaml.load(config, Loader=yaml.FullLoader)
            custom_print("Parameter server read config successfully", INFO)
            config["ip"] = ip
            config["port"] = port

            eval_config_file = './evaluation/evaluation_config.yml'
            with open(eval_config_file, 'r') as eval_config:
            
                eval_config = yaml.load(eval_config, Loader=yaml.FullLoader)
                config['executor_ip'] = eval_config['executor_ip']
                config['executor_port'] = eval_config['executor_port']
                config['job_manager_ip'] = eval_config['job_manager_ip']
                config['job_manager_port'] = eval_config['job_manager_port']
                config['dispatcher_use_docker'] = eval_config['dispatcher_use_docker']
                config['sched_alg'] = eval_config['sched_alg']
                config['do_compute'] = eval_config['do_compute']
                config['speedup_factor'] = eval_config['speedup_factor']
                # config['model_size'] = 10
                asyncio.run(run(config))
                
        except Exception as e:
            custom_print(e, ERROR)
        finally:
            asyncio.run(*_cleanup_coroutines)
