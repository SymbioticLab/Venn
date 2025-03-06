"""python examples/simple/client.py"""

from propius.controller.client import Propius_client

public_spec = {
    "cpu_f": 8,
    "ram": 6,
    "fp16_mem": 800,
    "android_os": 8
}


client_config = {
    "public_specifications": public_spec,
    "private_specifications": {
        "dataset_size_dummy": 1000,
    },
    "load_balancer_ip": "localhost",
    "load_balancer_port": 50002,
    "option": 0.0,
}

propius = Propius_client(client_config)


def select_task(task_ids, task_private_constraints):
    # select task according to local private constraints
    pass


while True:
    # make system calls to get device condition
    condition = True
    if condition:
        propius.connect()

        propius.client_check_in()

        task_ids, task_private_constraints = propius.client_ping(num_trial=5)

        task_id = select_task(task_ids, task_private_constraints)

        result = propius.client_accept(task_id)
        if result:
            job_ip, job_port = result[0], result[1]
        else:
            break

        propius.close()

        # check-in to job
        # receive task
        # perform task
        # report to job
