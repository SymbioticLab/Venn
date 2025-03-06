import sys
[sys.path.append(i) for i in ['.', '..', '...']]
import asyncio
import yaml
import pickle
import grpc
from evaluation.job.channels import parameter_server_pb2_grpc
from evaluation.job.channels import parameter_server_pb2
from propius.controller.client.propius_client_aio import Propius_client_aio
from evaluation.commons import *
from propius.controller.util.commons import *
from collections import deque
import time
import os
import csv
import random

class Client:
    def __init__(self, client_config: dict):
        self.id = client_config["id"] + client_config["dispatcher_id"] * client_config["dispatcher_cnt"]
        self.selection_method = client_config["selection_method"]

        if self.selection_method == "static_partition":
            self.partition_config = client_config["partition_config"]

        self.task_id = -1
        self.dispatcher_use_docker = client_config["dispatcher_use_docker"]

        if client_config["dispatcher_use_docker"]:
            client_config["load_balancer_ip"] = "load_balancer"

        self.comp_speed = client_config["computation_speed"]
        self.comm_speed = client_config["communication_speed"]

        client_config["option"] = 1/self.comp_speed if self.comp_speed > 0 else 0
            
        self.propius_client_stub = Propius_client_aio(
            client_config=client_config, 
            verbose=client_config['verbose'] if 'verbose' in client_config else False,
            logging=True)
        
        self.ps_channel = None
        self.ps_stub = None
        
        self.execution_duration = 3
        self.event_queue = deque()
        self.meta_queue = deque()
        self.data_queue = deque()
        self.round = 0

        self.eval_start_time = client_config["eval_start_time"] if "eval_start_time" in client_config else time.time()
        self.active_time = client_config["active"]
        self.inactive_time = client_config["inactive"]
        self.utilize_time = 0
        self.cur_period = 0
        self.speedup_factor = client_config["speedup_factor"]
        self.is_FA = client_config["is_FA"]

        self.local_steps = 0
        self.verbose = client_config['verbose'] if 'verbose' in client_config else False

        self.update_model_comm_time = 0
        self.upload_model_comm_time = 0

        self.client_result_path = client_config["client_result_path"]

        self.total_job = client_config["total_job"]
        self.job_driver_ip = client_config["job_driver_ip"]
        self.job_driver_starting_port = client_config["job_driver_starting_port"]
        self.job_profile_folder = client_config["job_profile_folder"]
        self.public_spec = client_config["public_specifications"]
        self.private_spec = client_config["private_specifications"]

    def _deallocate(self):
        self.event_queue.clear()
        self.meta_queue.clear()
        self.data_queue.clear()
    
    async def _connect_to_ps(self, ps_ip: str, ps_port: int):
        self.ps_channel = grpc.aio.insecure_channel(f"{ps_ip}:{ps_port}")
        self.ps_stub = parameter_server_pb2_grpc.Parameter_serverStub(self.ps_channel)
        custom_print(
            f"c-{self.id}: connecting to parameter server on {ps_ip}:{ps_port}")
        
    def _determine_eligiblity(self, job_id):
        profile_path = os.path.join(self.job_profile_folder, f"job_{job_id}.yml")
        with open(str(profile_path), 'r') as job_config_yaml:
            job_config = yaml.load(job_config_yaml, Loader=yaml.FullLoader)
            job_public_constraint = job_config["public_constraint"]
            job_private_constraint = job_config["private_constraint"]

        encoded_public_job, encoded_private_job = encode_specs(
            **job_public_constraint, **job_private_constraint
        )
        encoded_public_client, encoded_private_client = encode_specs(
            **self.public_spec, **self.private_spec
        )
        
        return geq(encoded_public_client, encoded_public_job) and geq(encoded_private_client, encoded_private_job)

    def _get_demand(self, job_id):
        profile_path = os.path.join(self.job_profile_folder, f"job_{job_id}.yml")
        with open(str(profile_path), 'r') as job_config_yaml:
            job_config = yaml.load(job_config_yaml, Loader=yaml.FullLoader)
            return job_config["demand"]

    async def handle_server_response(self, server_response: parameter_server_pb2.server_response):
        event = server_response.event
        meta = pickle.loads(server_response.meta)
        data = pickle.loads(server_response.data)
        self.event_queue.append(event)
        self.meta_queue.append(meta)
        self.data_queue.append(data)

    async def client_checkin(self)->bool:
        client_id_msg = parameter_server_pb2.client_id(
            id=self.propius_client_stub.id if self.selection_method == "propius" else self.id
        )
        server_response = await self.ps_stub.CLIENT_CHECKIN(client_id_msg)
        return server_response.event == DUMMY_EVENT
        
    async def client_ping(self)->bool:
        client_id_msg = parameter_server_pb2.client_id(
           id=self.propius_client_stub.id if self.selection_method == "propius" else self.id)
        server_response = await self.ps_stub.CLIENT_PING(client_id_msg)
        if server_response.event == DUMMY_EVENT:
            return True
        await self.handle_server_response(server_response)
        return False
    
    async def client_execute_complete(self, compl_event: str, status: bool, meta: str, data: str):
        client_complete_msg = parameter_server_pb2.client_complete(
            id=self.propius_client_stub.id if self.selection_method == "propius" else self.id,
            event=compl_event,
            status=status,
            meta=pickle.dumps(meta),
            data=pickle.dumps(data)
        )
        server_response = await self.ps_stub.CLIENT_EXECUTE_COMPLETION(client_complete_msg)
        await self.handle_server_response(server_response)

    async def execute(self)->bool:
        if len(self.event_queue) == 0:
            return False
        event = self.event_queue.popleft()
        meta = self.meta_queue.popleft()
        data = self.data_queue.popleft()
    
        exe_time = 0

        if event == CLIENT_TRAIN:
            self.local_steps = meta["local_steps"]
            one_step_exe_time = max(3 * meta["batch_size"] * float(self.comp_speed) / (1000 * self.speedup_factor), 0.0001)

            remain_time = self.remain_time()

            if meta["gradient_policy"] == 'fed-prox':
                self.local_steps = max(min(self.local_steps, int((remain_time - self.upload_model_comm_time) / one_step_exe_time)), 1)

            exe_time = one_step_exe_time * self.local_steps

            if meta["gradient_policy"] != 'fed-prox':
                if exe_time + self.upload_model_comm_time > remain_time:
                    return False

            if self.is_FA:
                exe_time /= 3

        elif event == SHUT_DOWN:
            return False
        
        elif event == UPDATE_MODEL:
            self.round = meta["round"]
            self.update_model_comm_time = meta["download_size"] / (float(self.comm_speed) * self.speedup_factor)
            self.upload_model_comm_time = meta["upload_size"] / (float(self.comm_speed) * self.speedup_factor)
            exe_time = self.update_model_comm_time

        elif event == UPLOAD_MODEL:
            exe_time = self.upload_model_comm_time
            if self.is_FA:
                exe_time = 0 

        custom_print(f"c-{self.id}: Recieve {event} event, executing for {exe_time} seconds", INFO)
        await asyncio.sleep(exe_time)

        self.utilize_time += exe_time * self.speedup_factor
        compl_event = event
        status = True
        compl_meta = {"round": self.round, "exec_id": self.id, "local_steps": self.local_steps}
        compl_data = DUMMY_RESPONSE
        
        await self.client_execute_complete(compl_event, status, compl_meta, compl_data)
        return True
    
    def remain_time(self) -> float:
        cur_time = time.time() - self.eval_start_time
        remain_time = self.inactive_time[self.cur_period] - cur_time
        return remain_time

    async def event_monitor(self):
        if not await self.client_checkin():
            await asyncio.sleep(3)
            return
        
        await asyncio.sleep(3)

        if self.verbose:
            custom_print(f"c-{self.id}: checked in")

        for _ in range(50):
            if not await self.client_ping():
                break
            await asyncio.sleep(3)

        if self.verbose:
            custom_print(f"c-{self.id}: executing")

        for _ in range(10):  
            if not await self.execute():
                break
            await asyncio.sleep(3)

    async def cleanup_routines(self, propius=False):
        try:
            self._deallocate()
            if propius:
                await self.propius_client_stub.close()
                custom_print(f"c-{self.id}: ==shutting down==", ERROR)
            await self.ps_channel.close()
        except Exception:
            pass

    async def run(self):
        try:
            status = False
            if self.selection_method == "static_partition":
                status = self.partition_config["status"]
                ps_ip, ps_port = self.partition_config["ps_ip"], self.partition_config["ps_port"]       

            while True:
                try:
                    if self.cur_period >= len(self.active_time) or \
                        self.cur_period >= len(self.inactive_time):
                        custom_print(f"Period: {self.cur_period}", ERROR)
                        custom_print(f"Active time: {self.active_time[-1]}", ERROR)
                        custom_print(f"Inactive time: {self.inactive_time[-1]}", ERROR)
                        custom_print(f"c-{self.id}: ==shutting down==", WARNING)
                        break
                    cur_time = time.time() - self.eval_start_time

                    if self.active_time[self.cur_period] > self.inactive_time[self.cur_period]:
                        custom_print(f"Period: {self.cur_period}", ERROR)
                        custom_print(f"Active time: {self.active_time}", ERROR)
                        custom_print(f"Inactive time: {self.inactive_time}", ERROR)
                        break
                    
                    if cur_time < self.active_time[self.cur_period]:
                        sleep_time = self.active_time[self.cur_period] - cur_time
                        # custom_print(f"c-{self.id}: sleep for {sleep_time}")
                        await asyncio.sleep(sleep_time)
                        continue
                    elif cur_time >= self.inactive_time[self.cur_period]:
                        self.cur_period += 1
                        continue

                    
                    # remain_time = self.remain_time()
                    # if remain_time <= 600 / self.speedup_factor:
                    #     await asyncio.sleep(remain_time)
                    #     continue

                    if self.selection_method == "propius":
                        await self.propius_client_stub.connect()
                        result = await self.propius_client_stub.auto_assign(ttl=5)
                        _, status, self.task_id, ps_ip, ps_port, _ = result
                        await self.propius_client_stub.close()
                    elif self.selection_method == "random":
                        ps_ip = self.job_driver_ip
                        job_id = random.randint(0, self.total_job - 1)
                        ps_port = self.job_driver_starting_port + job_id
                        status = self._determine_eligiblity(job_id)
                    
                    if not status:
                        sleep_time = 20
                        sleep_time /= self.speedup_factor
                        await asyncio.sleep(sleep_time)
                        continue
                    
                    await self._connect_to_ps(ps_ip, ps_port)
                    if self.verbose:
                        custom_print(f"c-{self.id}: connecting to {ps_ip}:{ps_port}")

                    await self.event_monitor()

                    if self.verbose:
                        custom_print(f"c-{self.id}: disconnect from {ps_ip}:{ps_port}")
                except Exception as e:
                    custom_print(f"c-{self.id}: {e}", ERROR)
                    await asyncio.sleep(1)
        finally:
            total_time = 0
            for i in range(0, min(self.cur_period, len(self.active_time))):
                total_time += (self.inactive_time[i] - self.active_time[i]) * self.speedup_factor
            if self.cur_period < len(self.active_time):
                cur_time = time.time() - self.eval_start_time
                if cur_time >= self.active_time[self.cur_period]:
                    total_time += (cur_time - self.active_time[self.cur_period]) * self.speedup_factor
            
            csv_file_name = self.client_result_path
            os.makedirs(os.path.dirname(csv_file_name), exist_ok=True)
            with open(csv_file_name, mode="a", newline="") as csv_file:
                writer = csv.writer(csv_file)
                writer.writerow([self.utilize_time, total_time])

            custom_print(f"c-{self.id}: utilize_time/active_time: {self.utilize_time}/{total_time}", WARNING)
            
            await self.cleanup_routines(propius=(self.selection_method == "propius"))
        
if __name__ == '__main__':
    config_file = './evaluation/client/test_client_conf.yml'
    with open(config_file, 'r') as config:
        config = yaml.load(config, Loader=yaml.FullLoader)
        if len(sys.argv) != 2:
            custom_print(f"Usage: python evaluation/client/client.py <id>", ERROR)
            exit(1)
        config["id"] = int(sys.argv[1])
        eval_config_file = './evaluation/evaluation_config.yml'
        with open(eval_config_file, 'r') as eval_config:
            eval_config = yaml.load(eval_config, Loader=yaml.FullLoader)
            config["load_balancer_ip"] = eval_config["load_balancer_ip"]
            config["load_balancer_port"] = eval_config["load_balancer_port"]
            config["dispatcher_use_docker"] = eval_config["dispatcher_use_docker"]
            config["eval_start_time"] = time.time()
            config["speedup_factor"] = 1
            config["is_FA"] = False
            config["verbose"] = True
            config["client_result_path"] = eval_config["client_result_path"]

            config["selection_method"] = eval_config["selection_method"]
            config["total_job"] = eval_config["total_job"]
            config["job_profile_folder"] = eval_config["profile_folder"]
            config["job_driver_ip"] = eval_config["job_driver_ip"]
            config["job_driver_starting_port"] = eval_config["job_driver_starting_port"]
            config["dispatcher_id"] = 0
            config["dispatcher_cnt"] = 0
            config["partition_config"] = {
                "status": False,
                "ps_ip": eval_config["job_driver_ip"],
                "ps_port": eval_config["job_driver_starting_port"]
            }
            client = Client(config)
            asyncio.run(client.run())
     

