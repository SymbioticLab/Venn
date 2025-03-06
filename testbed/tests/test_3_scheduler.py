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
import signal
import atexit
import pytest

@pytest.fixture
def setup_and_teardown_for_stuff():
    process = []
    print("\nsetting up")
    init(process)
    yield
    print("\ntearing down")
    clean_up(process)


def job_register(gconfig, cst_dict=None):
    jm_ip = gconfig["job_manager_ip"]
    jm_port = gconfig["job_manager_port"]

    job_config = {
        "public_constraint": {"cpu_f": 0, "ram": 0, "fp16_mem": 0, "android_os": 0}
        if cst_dict is None
        else cst_dict,
        "private_constraint": {
            "dataset_size_dummy": 100,
        },
        "total_round": 10,
        "demand": 5,
        "job_manager_ip": jm_ip,
        "job_manager_port": jm_port,
        "ip": "localhost",
        "port": 6000,
    }
    propius_stub = Propius_job(job_config=job_config, verbose=True, logging=True)

    if not propius_stub.register():
        print(f"Parameter server: register failed")

    return propius_stub


def client_ping(gconfig, public_spec):
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
    propius_client.client_check_in()

    task_ids = []
    for _ in range(3):
        task_ids, _ = propius_client.client_ping(1)
        if task_ids:
            break
        else:
            time.sleep(2)
    return task_ids


def test_scheduler(setup_and_teardown_for_stuff):
    with open(GLOBAL_CONFIG_FILE, "r") as gconfig:
        gconfig = yaml.load(gconfig, Loader=yaml.FullLoader)
        logger = Propius_logger("test", log_file=None, verbose=True, use_logging=False)
        job_db = SC_job_db_portal(gconfig, logger)
        job_db.flushdb()

        sched_alg = gconfig["sched_alg"]
        sched_mode = gconfig["sched_mode"]

        if sched_mode == "online":
            if sched_alg == "fifo":
                fifo(gconfig, job_db)
            elif sched_alg == "random":
                random(gconfig, job_db)
            elif sched_alg == "srsf":
                srsf(gconfig, job_db)
        elif sched_mode == "offline":
            if sched_alg == "fifo":
                offline_fifo(gconfig)


def offline_fifo(gconfig):
    time.sleep(1)
    job = job_register(gconfig, {"cpu_f": 2, "ram": 2, "fp16_mem": 2, "android_os": 2})
    job.start_request()
    time.sleep(0.1)
    job = job_register(gconfig, {"cpu_f": 5, "ram": 2, "fp16_mem": 2, "android_os": 2})
    job.start_request()
    time.sleep(0.1)
    job = job_register(gconfig, {"cpu_f": 1, "ram": 2, "fp16_mem": 2, "android_os": 2})
    job.start_request()
    time.sleep(0.1)
    task_ids = client_ping(
        gconfig, {"cpu_f": 3, "ram": 3, "fp16_mem": 3, "android_os": 3}
    )

    assert len(task_ids) == 2
    assert task_ids == [0, 2]


def fifo(gconfig, job_db):
    time.sleep(1)
    job_register(gconfig)
    time.sleep(0.1)
    score1 = float(job_db.get_field(0, "score"))

    time.sleep(1)
    job_register(gconfig)
    time.sleep(0.1)
    score2 = float(job_db.get_field(1, "score"))

    time.sleep(1)
    job_register(gconfig)
    time.sleep(0.1)
    score3 = float(job_db.get_field(2, "score"))

    assert score1 > score2
    assert score2 > score3


def random(gconfig, job_db):
    time.sleep(1)
    job_register(gconfig)
    time.sleep(0.1)
    score1 = float(job_db.get_field(0, "score"))
    assert score1 != 0.0

    time.sleep(1)
    job_register(gconfig)
    time.sleep(0.1)
    score2 = float(job_db.get_field(1, "score"))
    assert score1 != score2


def srsf(gconfig, job_db):
    time.sleep(1)
    propius_stub = job_register(gconfig)
    propius_stub.start_request()
    time.sleep(0.1)
    score1 = float(job_db.get_field(0, "score"))
    assert score1 == -5

    time.sleep(1)
    propius_stub = job_register(gconfig)
    propius_stub.start_request(new_demand=True, demand=10)
    time.sleep(0.1)
    score2 = float(job_db.get_field(1, "score"))
    assert score2 == -10
