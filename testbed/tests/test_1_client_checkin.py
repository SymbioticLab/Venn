import subprocess
from propius.controller.scheduler.sc_db_portal import SC_job_db_portal
from propius.controller.config import GLOBAL_CONFIG_FILE
from propius.controller.job.propius_job import Propius_job
from propius.controller.util import Msg_level, Propius_logger
from propius.controller.client.propius_client import Propius_client
from propius.util import init, clean_up
import yaml
import time
import os
import pytest


@pytest.fixture
def setup_and_teardown_for_stuff():
    process = []
    print("\nsetting up")
    init(process)
    yield
    print("\ntearing down")
    clean_up(process)


def job_request(gconfig, demand):
    jm_ip = gconfig["job_manager_ip"]
    jm_port = gconfig["job_manager_port"]

    job_config = {
        "public_constraint": {"cpu_f": 3, "ram": 3, "fp16_mem": 3, "android_os": 3},
        "private_constraint": {
            "dataset_size_dummy": 100,
        },
        "total_round": 10,
        "demand": demand,
        "job_manager_ip": jm_ip,
        "job_manager_port": jm_port,
        "ip": "localhost",
        "port": 6000,
    }
    propius_stub = Propius_job(job_config=job_config, verbose=True, logging=True)

    if not propius_stub.register():
        print(f"Parameter server: register failed")
        return None

    assert propius_stub.start_request() == 0

    return propius_stub


def client_check_in(gconfig, public_spec):
    lb_ip = gconfig["load_balancer_ip"]
    lb_port = gconfig["load_balancer_port"]
    client_config = {
        "public_specifications": public_spec,
        "private_specifications": {
            "dataset_size_dummy": 1000,
        },
        "load_balancer_ip": lb_ip,
        "load_balancer_port": lb_port,
        "option": 0.0,
    }

    propius_client = Propius_client(client_config=client_config, verbose=True)
    propius_client.connect()
    return propius_client.client_check_in()


def test_client_check_in(setup_and_teardown_for_stuff):
    with open(GLOBAL_CONFIG_FILE, "r") as gconfig:
        gconfig = yaml.load(gconfig, Loader=yaml.FullLoader)

        sched_alg = gconfig["sched_alg"]
        sched_mode = gconfig["sched_mode"]
        time.sleep(1)
        job_request(gconfig, 5)
        time.sleep(1)
        task_offer, constraints = client_check_in(
            gconfig, {"cpu_f": 4, "ram": 5, "fp16_mem": 6, "android_os": 7}
        )
        if sched_mode == "online":
            assert task_offer == [0]
            # assert constraints == [(100,)]
        elif sched_mode == "offline":
            assert task_offer == []

        task_offer, constraints = client_check_in(
            gconfig, {"cpu_f": 1, "ram": 5, "fp16_mem": 6, "android_os": 7}
        )
        assert task_offer == []
        assert constraints == []

        if sched_alg == "fifo":
            job_request(gconfig, 5)
            time.sleep(1)

            task_offer, constraints = client_check_in(
                gconfig, {"cpu_f": 4, "ram": 5, "fp16_mem": 6, "android_os": 7}
            )
            if sched_mode == "online":
                assert task_offer == [0, 1]
                # assert constraints == [(100,), (100,)]
            elif sched_mode == "offline":
                assert task_offer == []

        elif sched_alg == "srsf":
            job_request(gconfig, 3)
            time.sleep(1)

            task_offer, constraints = client_check_in(
                gconfig, {"cpu_f": 4, "ram": 5, "fp16_mem": 6, "android_os": 7}
            )
            assert task_offer == [1, 0]
            # assert constraints == [(100,), (100,)]
