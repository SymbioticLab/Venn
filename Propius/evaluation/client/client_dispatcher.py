import sys
[sys.path.append(i) for i in ['.', '..', '...']]
# import matplotlib.pyplot as plt
import time
import random
import asyncio
import yaml
import logging
import logging.handlers
import pickle
import os
import csv
from evaluation.client.client import *
from propius.controller.util.commons import *

# static_partitioning
alloc = [20, 40, 40, 80, 160]
alloc_cnt = [0, 0, 0, 0, 0]

def _determine_eligiblity(job_profile_folder, job_id, public_spec, private_spec):
        profile_path = os.path.join(job_profile_folder, f"job_{job_id}.yml")
        with open(str(profile_path), 'r') as job_config_yaml:
            job_config = yaml.load(job_config_yaml, Loader=yaml.FullLoader)
            job_public_constraint = job_config["public_constraint"]
            job_private_constraint = job_config["private_constraint"]

        encoded_public_job, encoded_private_job = encode_specs(
            **job_public_constraint, **job_private_constraint
        )
        encoded_public_client, encoded_private_client = encode_specs(
            **public_spec, **private_spec
        )
        
        return geq(encoded_public_client, encoded_public_job) and geq(encoded_private_client, encoded_private_job)


async def run(config):
    public_constraint_name = config['job_public_constraint']
    private_constraint_name = config['job_private_constraint']
    ideal_client = config['ideal_client']

    client_comm_dict = None
    with open(config['client_comm_path'], 'rb') as client_file:
        client_comm_dict = pickle.load(client_file)

    client_spec_dict = None
    with open(config['client_spec_path'], 'rb') as client_file:
        client_spec_dict = pickle.load(client_file)

    client_size_dict = None
    with open(config['client_size_path'], 'rb') as client_file:
        client_size_dict = pickle.load(client_file)

    client_avail_dict = None
    with open(config['client_avail_path'], 'rb') as client_file:
        client_avail_dict = pickle.load(client_file)
    client_num = config['client_num']

    eval_start_time = time.time()

    task_list = []
    total_client_num = len(client_avail_dict)

    await asyncio.sleep(10)

    try:
        for id in range(client_num):
            client_idx = random.randint(0, total_client_num - 1)
            public_specs = {
                name: client_spec_dict[client_idx % len(client_spec_dict)][name]
                for name in public_constraint_name}
            private_specs = {
                "dataset_size_dummy": client_size_dict[client_idx % len(client_size_dict)]}
            
            # static partition
            partition_config = {
                "status": False,
                "ps_ip": config["job_driver_ip"],
                "ps_port": config["job_driver_starting_port"],
            }

            if config["selection_method"] == "static_partition":
                elig_job = []
                for job_id in range(0, config["total_job"]):
                    if _determine_eligiblity(config["profile_folder"], job_id, public_specs, private_specs):
                        elig_job.append(job_id)

                if elig_job:
                    elig_job.reverse()
                    job_id = random.choice(elig_job)

                    for i in elig_job:
                        if alloc_cnt[i] < alloc[i]:
                            alloc_cnt[i] += 1
                            job_id = i
                            break

                    partition_config = {
                        "status": True,
                        "ps_ip": config["job_driver_ip"],
                        "ps_port":config["job_driver_starting_port"] + job_id,
                    }

            if ideal_client:
                active_time = [0]
                inactive_time = [3600 * 24 * 7]
            else:
                active_time = [ x/config['speedup_factor'] for x in client_avail_dict[client_idx + 1]['active']]
                inactive_time = [ x/config['speedup_factor'] for x in client_avail_dict[client_idx + 1]['inactive']] 
            client_config = {
                "id": id,
                "public_specifications": public_specs,
                "private_specifications": private_specs,
                "load_balancer_ip": config['load_balancer_ip'],
                "load_balancer_port": config['load_balancer_port'],
                "computation_speed": client_spec_dict[client_idx % len(client_spec_dict)]['speed'],
                "communication_speed": client_comm_dict[client_idx % len(client_comm_dict) + 1]['communication'],
                "eval_start_time": eval_start_time,
                "active": active_time,
                "inactive": inactive_time,
                "dispatcher_use_docker": config["dispatcher_use_docker"],
                "speedup_factor": config["speedup_factor"],
                "is_FA": config["is_FA"],
                "verbose": False,
                "client_result_path": config["client_result_path"],
                "selection_method": config["selection_method"],
                "total_job": config["total_job"],
                "job_profile_folder": config["profile_folder"],
                "job_driver_ip": config["job_driver_ip"],
                "job_driver_starting_port": config["job_driver_starting_port"],
                "dispatcher_id": config["dispatcher_id"],
                "dispatcher_cnt": client_num,
                "partition_config": partition_config
            }
            task = asyncio.create_task(Client(client_config).run())
            task_list.append(task)
        print(alloc_cnt)
        while True:
            await asyncio.sleep(10)
    except KeyboardInterrupt:
        print("Cancelled")
        for task in task_list:
            task.cancel()

    finally:
        await asyncio.gather(*task_list, return_exceptions=True)

if __name__ == '__main__':
    client_num = int(sys.argv[1])
    dispatcher_id = int(sys.argv[2])

    log_file = f'./evaluation/monitor/client/dispatcher_{dispatcher_id}.log'

    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    handler = logging.handlers.RotatingFileHandler(log_file, maxBytes=5000000, backupCount=5)

    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    root_logger = logging.getLogger()
    root_logger.addHandler(handler)
    root_logger.setLevel(logging.INFO)

    setup_file = './evaluation/evaluation_config.yml'

    random.seed(42)

    with open(setup_file, "r") as yamlfile:
        try:
            config = yaml.load(yamlfile, Loader=yaml.FullLoader)
            config["client_num"] = client_num
            config["dispatcher_id"] = dispatcher_id

            # init result report
            # csv_file_name = config["client_result_path"]
            # os.makedirs(os.path.dirname(csv_file_name), exist_ok=True)
            # fieldnames = ["utilize_time", "active_time"]
            # with open(csv_file_name, "w", newline="") as csv_file:
            #     writer = csv.writer(csv_file)
            #     writer.writerow(fieldnames)

            asyncio.run(run(config))
        except KeyboardInterrupt:
            pass
        except Exception as e:
            custom_print(e, ERROR)
        finally:
            pass