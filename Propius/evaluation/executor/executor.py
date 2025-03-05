import sys
[sys.path.append(i) for i in ['.', '..', '...']]
import asyncio
import yaml
import grpc
import pickle
import math
from evaluation.executor.channels import executor_pb2
from evaluation.executor.channels import executor_pb2_grpc
from evaluation.executor.task_pool import *
from evaluation.executor.worker_manager import *
from evaluation.commons import *
import os
import logging
import logging.handlers

_cleanup_coroutines = []

class Executor(executor_pb2_grpc.ExecutorServicer):
    def __init__(self, config: dict, logger: My_logger):
        self.ip = config['executor_ip'] if not config['use_docker'] else '0.0.0.0'
        self.port = config['executor_port']
        self.task_pool = Task_pool(config)
        self.worker = Worker_manager(config, logger)
        self.sched_alg = config['sched_alg']
        self.config = config
        self.round_timeout = config['round_timeout']

        self.logger = logger
        self.job_train_task_dict = {}
        self.job_test_task_dict = {}

    async def JOB_REGISTER(self, request, context):
        job_id = request.job_id
        job_meta = pickle.loads(request.job_meta)

        model_size = await self.worker.init_job(job_id=job_id, 
                                   dataset_name=job_meta["dataset"],
                                   model_name=job_meta["model"],
                                   args=job_meta
                                   )
        self.logger.print(f"job {job_id} registered", INFO)
        await self.task_pool.init_job(job_id, job_meta)            
        return executor_pb2.register_ack(ack=True, model_size=model_size)
    
    async def JOB_REGISTER_TASK(self, request, context):
        job_id, client_id = request.job_id, request.client_id
        round, event = request.round, request.event
        task_meta = pickle.loads(request.task_meta)

        await self.task_pool.insert_job_task(job_id=job_id, 
                                             client_id=client_id,
                                             round=round,
                                             event=event,
                                             task_meta=task_meta)
                
        # self.logger.print(f"Executer: job {job_id} {event} registered", INFO)
        return executor_pb2.ack(ack=True)

    async def wait_for_testing_task(self, job_id:int):
        if job_id not in self.job_test_task_dict:
            return
        task_list = self.job_test_task_dict[job_id]
        self.job_test_task_dict[job_id] = []
        if len(task_list) > 0:
            try:
                completed, pending = await asyncio.wait(task_list,
                                                        timeout=self.round_timeout,
                                                        return_when=asyncio.ALL_COMPLETED)
                for task in completed:
                    try:
                        await task
                    except Exception as e:
                        self.logger.print(e, ERROR)
            except Exception as e:
                self.logger.print(e, ERROR)

    
    async def wait_for_training_task(self, job_id:int):
        if job_id not in self.job_train_task_dict:
            return
        task_list = self.job_train_task_dict[job_id]
        self.job_train_task_dict[job_id] = []

        if len(task_list) > 0:
            try:
                completed, pending = await asyncio.wait(task_list,
                                                    timeout=self.round_timeout,
                                                    return_when=asyncio.ALL_COMPLETED)
                for task in completed:
                    try:
                        await task
                    except Exception as e:
                        self.logger.print(e, ERROR)
                        
            except Exception as e:
                self.logger.print(e, ERROR)

    async def execute(self):
        while True:
            execute_meta = await self.task_pool.get_next_task()
            
            if not execute_meta:
                await asyncio.sleep(3)
                continue
            
            job_id = execute_meta['job_id']
            client_id_list = execute_meta['client_id_list']
            event = execute_meta['event']
            round = execute_meta['round']

            del execute_meta['job_id']
            del execute_meta['client_id_list']
            del execute_meta['event']
            del execute_meta['round']

            self.logger.print(f"Execute job {job_id}-{round}-{event} " 
                            f"list_size: {len(client_id_list)}", INFO)

            if event == JOB_FINISH:
                try:
                    await self.wait_for_training_task(job_id=job_id)
                    await self.wait_for_testing_task(job_id=job_id)
                    await self.task_pool.remove_job(job_id=job_id)
                    await self.worker.remove_job(job_id=job_id)
                    
                    if job_id in self.job_train_task_dict:
                        del self.job_train_task_dict[job_id]
                    if job_id in self.job_test_task_dict:
                        del self.job_test_task_dict[job_id]
                except Exception as e:
                    self.logger.print(e, ERROR)

                continue
            
            elif event == CLIENT_TRAIN:
                # create asyncio task for testing task
                task = asyncio.create_task(
                    self.worker.execute(event=CLIENT_TRAIN,
                                          job_id=job_id,
                                          round=round,
                                          client_id_list=client_id_list,
                                          args=execute_meta)
                )

                if job_id not in self.job_train_task_dict:
                    self.job_train_task_dict[job_id] = []
                self.job_train_task_dict[job_id].append(task)

                if len(self.job_train_task_dict[job_id]) >= 5 * self.worker.worker_num:
                    await self.wait_for_training_task(job_id=job_id)

            elif event == MODEL_TEST:
                await self.wait_for_training_task(job_id=job_id)

                if job_id not in self.job_test_task_dict:
                    self.job_test_task_dict[job_id] = []
                
                client_test_num = self.config["client_test_num"]
                client_test_list = list(range(client_test_num))
                worker_test_num = int(client_test_num / self.worker.worker_num)
                for i in range(self.worker.worker_num):
                    if i == self.worker.worker_num - 1:
                        client_id_list = client_test_list[i*worker_test_num:-1]
                    else:
                        client_id_list = client_test_list[i*worker_test_num:(i+1)*worker_test_num]

                    task = asyncio.create_task(
                        self.worker.execute(event=MODEL_TEST,
                                            job_id=job_id,
                                            client_id_list=client_id_list,
                                            round=round,
                                            args=execute_meta)
                    )
                    self.job_test_task_dict[job_id].append(task)
                    if len(self.job_test_task_dict[job_id]) >= 5 * self.worker.worker_num:
                        await self.wait_for_testing_task(job_id=job_id)

            elif event == AGGREGATE:
                # wait for all pending training task to complete
                await self.wait_for_training_task(job_id=job_id)
                try:
                    results = await self.worker.execute(event=AGGREGATE,
                                                        job_id=job_id,
                                                        client_id_list=[],
                                                        round=round,
                                                        args=execute_meta)
                
                    await self.task_pool.report_result(job_id=job_id,
                                                    round=round,
                                                    result=results,
                                                    is_train=True)
                except Exception as e:
                    self.logger.print(e, ERROR)
                
            elif event == AGGREGATE_TEST:
                await self.wait_for_testing_task(job_id=job_id)
                try:
                    results = await self.worker.execute(event=AGGREGATE_TEST,
                                                        job_id=job_id,
                                                        client_id_list=[],
                                                        round=round,
                                                        args=execute_meta)
                    await self.task_pool.report_result(job_id=job_id,
                                                        round=round,
                                                        result=results,
                                                        is_train=False)
                except Exception as e:
                    self.logger.print(e, ERROR)
                
            elif event == ROUND_FAIL:
                # wait for all pending training task to complete                
                await self.wait_for_training_task(job_id=job_id)

                # clear aggregated weights for this round, no report generated

                try:
                    await self.worker.execute(event=ROUND_FAIL,
                                                job_id=job_id,
                                                client_id_list=[],
                                                round=round,
                                                args=execute_meta,)
                except Exception as e:
                    self.logger.print(e, ERROR)
    
async def run(config, logger):
    async def server_graceful_shutdown():
        logger.print("==Executor ending==", WARNING)
        heartbeat_task.cancel()
        await heartbeat_task
        await executor.worker._disconnect()
        await server.stop(5)

    server = grpc.aio.server()
    executor = Executor(config, logger)
    _cleanup_coroutines.append(server_graceful_shutdown())

    heartbeat_task = asyncio.create_task(executor.worker.heartbeat_routine())

    executor_pb2_grpc.add_ExecutorServicer_to_server(executor, server)
    server.add_insecure_port(f"{executor.ip}:{executor.port}")
    await server.start()
    logger.print(f"executor started, listening on {executor.ip}:{executor.port}", INFO)

    await executor.execute()

if __name__ == '__main__':
    log_file = './evaluation/monitor/executor/exe.log'
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    logger = My_logger(log_file=log_file, verbose=True, use_logging=True)

    config_file = './evaluation/evaluation_config.yml'
    with open(config_file, 'r') as config:
        try:
            config = yaml.load(config, Loader=yaml.FullLoader)
            logger.print("Executor read config successfully")
            
            loop = asyncio.get_event_loop()
            loop.run_until_complete(run(config, logger))
        except KeyboardInterrupt:
            pass
        except Exception as e:
            logger.print(e, ERROR)
        finally:
            loop.run_until_complete(*_cleanup_coroutines)
            loop.close()