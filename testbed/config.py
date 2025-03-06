import ruamel.yaml
import math
import random
import os
import copy

PROPIUS_SYS = 0
PROPIUS_POLICY = 1
PROPIUS_EVAL = 2

### EDIT HERE!

# Option can be PROPIUS_SYS, PROPIUS_POLICY, PROPIUS_EVAL
# PROPIUS_SYS: Run Propius system
# PROPIUS_POLICY: Run Propius policy evaluation
# PROPIUS_EVAL: Run Propius evaluation with ML workloads using GPU
option = PROPIUS_SYS

# Scheduler algorithm
sched_alg = "irs"

# Configuration file paths
propius_config_file = './propius/global_config.yml'
evaluation_config_file = './evaluation/evaluation_config.yml'

# If you want to use docker to run Propius, set propius_use_docker to True
propius_use_docker = True
# If you want to use docker to run evaluation workloads, set evaluation_use_docker to True
dispatcher_use_docker = True

# Set the number of client manager
client_manager_num = 2
client_manager_port_start = 50003
client_db_port_start = 6380

# Ideal client: no failure or straggler
ideal_client = False
# FA: federated analytics mode (only forward pass)
is_FA = False

# Speedup factor for the emulation
speedup_factor = 3

# Job profile folder
profile_folder = './evaluation/job/profile_dummy'

# Select job trace. The first column is the arrival time, the second column is the job id.
job_trace = './evaluation/job/trace/job_trace_4.txt'
allow_exceed_total_round = True

dataset = "femnist"


### STOP EDITING HERE!
if option == PROPIUS_SYS:
    compose_file = './compose_propius.yml'
    do_compute = False
    use_cuda = False
    evaluation_use_docker = False
else:
    total_job = 20
    client_num = 15000

    evaluation_use_docker = True

    client_per_container = 1000
    job_per_container = 2   
    if option == PROPIUS_POLICY:
        compose_file = './compose_eval.yml'
        do_compute = False
        use_cuda = False
    elif option == PROPIUS_EVAL:
        compose_file = './compose_eval_gpu.yml'
        do_compute = True
        use_cuda = True
        worker_num_list = [0, 0, 4, 4]
        worker_num = sum(worker_num_list)
        worker_starting_port = 49998

def cleanup():
    for i in range(100):
        if f'worker_{i}' in compose_data['services']:
            del compose_data['services'][f'worker_{i}']
        if f'jobs_{i}' in compose_data['services']:
            del compose_data['services'][f'jobs_{i}']
        if f'clients_{i}' in compose_data['services']:
            del compose_data['services'][f'clients_{i}']
        if f'client_db_{i}' in compose_data['services']:
            del compose_data['services'][f'client_db_{i}']
        if f'client_manager_{i}' in compose_data['services']:
            del compose_data['services'][f'client_manager_{i}']

def config_scheduler():
    compose_data['services']['scheduler']['depends_on'] = [
        f'client_db_{i}' for i in range(client_manager_num)
    ]
    compose_data['services']['scheduler']['depends_on'].append('job_db')

def config_job_manager():
    if option == PROPIUS_SYS:
        compose_data['services']['job_manager']['ports'] = ['50001:50001']
    else:
        if 'ports' in compose_data['services']['job_manager']:
            del compose_data['services']['job_manager']['ports']

def config_load_balancer():
    if option == PROPIUS_SYS:
        compose_data['services']['load_balancer']['ports'] = ['50002:50002']
    else:
        if 'ports' in compose_data['services']['load_balancer']:
            del compose_data['services']['load_balancer']['ports']
        
    compose_data['services']['load_balancer']['depends_on'] = [
        f'client_manager_{i}' for i in range(client_manager_num)
    ]

def config_client_manager_db():
    for i in range(client_manager_num):
        new_client_db_service = {
            f"client_db_{i}": {
                'build': {
                'context': '.',
                'dockerfile': './propius/controller/database/Dockerfile'
                },
                'command': [f'{client_db_port_start + i}'],
                'environment': ['TZ=America/Detroit']
            }
        }

        new_client_manger_service = {
            f"client_manager_{i}": {
                'build': {
                'context': '.',
                'dockerfile': './propius/controller/client_manager/Dockerfile'
                },
                'volumes': [
                    './propius:/propius'
                ],
                'depends_on': [
                    'job_db',
                    f'client_db_{i}',
                    'scheduler',
                ],
                'command': [f'{i}'],
                'environment': ['TZ=America/Detroit'],
                'stop_signal': 'SIGINT'
            }
        }
        compose_data['services'].update(new_client_manger_service)
        compose_data['services'].update(new_client_db_service)

def config_propius():
    propius_data["client_manager"] = [
    {"ip": "localhost",
     "port": client_manager_port_start + i,
     "client_db_port": client_db_port_start + i}
     for i in range(client_manager_num)
    ]
    propius_data["use_docker"] = propius_use_docker
    propius_data["verbose"] = True
    propius_data["sched_alg"] = sched_alg
    propius_data["allow_exceed_total_round"] = allow_exceed_total_round

    def get_gpu_idx(allocate_list):
        for i, _ in enumerate(allocate_list):
            if allocate_list[i] > 0:
                allocate_list[i] -= 1
                return i

    if option == PROPIUS_EVAL:
        allocate_list = copy.deepcopy(worker_num_list)
        config_data['worker'] = [{
            'ip': 'localhost',
            'port': worker_starting_port - i,
            'device': get_gpu_idx(allocate_list)
        } for i in range(worker_num)]

def config_evaluation():
    config_data["use_docker"] = evaluation_use_docker
    config_data["dispatcher_use_docker"] = dispatcher_use_docker
    config_data["do_compute"] = do_compute
    config_data["is_FA"] = is_FA
    config_data["use_cuda"] = use_cuda
    config_data["speedup_factor"] = speedup_factor
    config_data["sched_alg"] = sched_alg
    config_data["job_trace"] = job_trace
    config_data["profile_folder"] = profile_folder
    config_data["ideal_client"] = ideal_client

    if option in [PROPIUS_EVAL, PROPIUS_POLICY]:
        config_data["total_job"] = total_job
        config_data["client_num"] = client_num

    if dataset == 'femnist':
        config_data['data_dir'] = "./datasets/femnist"
        config_data['data_map_file'] = './datasets/femnist/client_data_mapping/train.csv'
        config_data['test_data_map_file'] = './datasets/femnist/client_data_mapping/test.csv'

    elif dataset == 'openImg':
        #TODO
        config_data['data_dir'] = './datasets/openImg'
        config_data['data_map_file'] = './datasets/openImg/client_data_mapping/train.csv'

def config_worker():
    for i in range(worker_num):
        new_service = {
            f'worker_{i}': {
                'build': {
                    'context': '.',
                    'dockerfile': './evaluation/executor/Dockerfile_worker_gpu',
                    'args': {
                        'WORKER_IMAGE': 'nvidia/cuda:11.6.2-devel-ubuntu20.04'
                    }
                },
                'volumes': [
                    './evaluation:/evaluation',
                    './datasets:/datasets',
                ],
                'stop_signal': 'SIGINT',
                'command': [f'{i}'],
                'deploy': {
                    'resources': {
                        'reservations': {
                            'devices':[{
                                    'driver': 'nvidia',
                                    'count': len(worker_num_list),
                                    'capabilities': ['gpu'],
                            }]
                        }
                    }
                },
                'environment': ['TZ=America/Detroit']
            }
        }
        compose_data['services'].update(new_service)
    
    compose_data['services']['executor']['depends_on'] = [
        f'worker_{i}' for i in range(worker_num)
    ]

def config_dispatcher():
    for i in range(math.ceil(total_job / job_per_container)):
        start_row = i * job_per_container
        end_row = min(total_job, start_row + job_per_container)

        new_job_container = {
            f'jobs_{i}': {
                'build': {
                    'context': '.',
                    'dockerfile': './evaluation/job/Dockerfile'
                },
                'volumes': [
                    './evaluation:/evaluation',
                    './propius:/propius',
                ],
                'stop_signal': 'SIGINT',
                'depends_on': [
                    'job_manager'
                ],
                'command': [
                    f'{start_row}',
                    f'{end_row}',
                    f'{i}'
                ],
                'environment': ['TZ=America/Detroit'],
            }
        }
        
        compose_data['services'].update(new_job_container)

    for i in range(math.ceil(client_num / client_per_container)):
        num = min(client_per_container, client_num - i * client_per_container)

        new_client_container = {
            f'clients_{i}': {
                'build': {
                    'context': '.',
                    'dockerfile': './evaluation/client/Dockerfile',
                },
                'volumes': [
                    './evaluation:/evaluation',
                    './datasets/device_info:/datasets/device_info',
                ],
                'stop_signal': 'SIGINT',
                'depends_on': [
                    'load_balancer'
                ],
                'environment': ['TZ=America/Detroit'],
                'command': [
                    f'{num}',
                    f'{i}'
                ],
            }
        }
        compose_data['services'].update(new_client_container)

yaml = ruamel.yaml.YAML()

with open(evaluation_config_file, 'r') as evaluation_config_yaml_file:
    config_data = yaml.load(evaluation_config_yaml_file)

with open(propius_config_file, 'r') as propius_config_yaml_file:
    propius_data = yaml.load(propius_config_yaml_file)

with open(compose_file, 'r') as compose_yaml_file:
    compose_data = yaml.load(compose_yaml_file)

cleanup()
config_scheduler()
config_job_manager()
config_load_balancer()
config_client_manager_db()
config_propius()
config_evaluation()
if option in [PROPIUS_POLICY, PROPIUS_EVAL]:
    config_dispatcher()
if option in [PROPIUS_EVAL]:
    config_worker()

with open(propius_config_file, 'w') as propius_config_yaml_file:
    yaml.dump(propius_data, propius_config_yaml_file) 

with open(evaluation_config_file, 'w') as evaluation_config_yaml_file:
    yaml.dump(config_data, evaluation_config_yaml_file)

with open(compose_file, 'w') as compose_yaml_file:
    yaml.dump(compose_data, compose_yaml_file)
