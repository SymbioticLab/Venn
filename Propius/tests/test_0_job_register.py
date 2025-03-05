import subprocess
from propius.controller.database.db import Job_db
from propius.controller.config import GLOBAL_CONFIG_FILE
from propius.controller.job.propius_job import Propius_job
from propius.controller.util import Msg_level, Propius_logger
from propius.util import clean_up, init
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


def job_register(gconfig):
    jm_ip = gconfig["job_manager_ip"]
    jm_port = gconfig["job_manager_port"]

    job_config = {
        "public_constraint": {"cpu_f": 0, "ram": 0, "fp16_mem": 0, "android_os": 0},
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


def test_register(setup_and_teardown_for_stuff):
    with open(GLOBAL_CONFIG_FILE, "r") as gconfig:
        gconfig = yaml.load(gconfig, Loader=yaml.FullLoader)
        logger = Propius_logger("test", log_file=None, verbose=True, use_logging=False)
        job_db = Job_db(gconfig, False, logger)

        time.sleep(1)
        job_register(gconfig)
        assert job_db.get_job_size() == 1

        time.sleep(1)
        job_register(gconfig)

        assert job_db.get_job_size() == 2
