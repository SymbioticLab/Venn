import subprocess
from propius.controller.scheduler.sc_db_portal import SC_job_db_portal
from propius.controller.config import GLOBAL_CONFIG_FILE
from propius.controller.job.propius_job import Propius_job
from propius.controller.util import Msg_level, Propius_logger
from propius.controller.client.propius_client import Propius_client
import yaml
import time
import os
import signal
import atexit


def init(process):
    try:
        p = subprocess.Popen(
            ["docker", "compose", "-f", "compose_redis.yml", "up", "-d"]
        )
        process.append(p.pid)

        p = subprocess.Popen(["python", "-m", "propius.controller.job_manager"])
        process.append(p.pid)

        p = subprocess.Popen(["python", "-m", "propius.controller.scheduler"])
        process.append(p.pid)

        p = subprocess.Popen(["python", "-m", "propius.controller.client_manager", "0"])
        process.append(p.pid)

        p = subprocess.Popen(["python", "-m", "propius.controller.client_manager", "1"])
        process.append(p.pid)

        p = subprocess.Popen(["python", "-m", "propius.controller.load_balancer"])
        process.append(p.pid)

    except subprocess.CalledProcessError as e:
        print(f"Error: {e}")


def init_ps(process):
    try:
        p = subprocess.Popen(["propius-parameter-server-root"])
        process.append(p.pid)

        p = subprocess.Popen(["propius-parameter-server-leaf"])
        process.append(p.pid)
    except subprocess.CalledProcessError as e:
        print(f"Error: {e}")


def clean_up(process):
    for p in process:
        try:
            os.kill(p, signal.SIGTERM)
        except Exception as e:
            print(e)
