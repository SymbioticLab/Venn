"""python examples/simple/job.py"""

from propius.controller.job import Propius_job

job_config = {
    "public_constraint": {"cpu_f": 0, "ram": 0, "fp16_mem": 0, "android_os": 0},
    "private_constraint": {
        "dataset_size_dummy": 100,
    },
    "total_round": 1,
    "demand": 2,
    "job_manager_ip": "localhost",
    "job_manager_port": "50001",
    "ip": "localhost",
    "port": 6000,
}
propius = Propius_job(job_config)

propius.connect()
propius.register()

for round in range(job_config["total_round"]):
    propius.start_request()
    # client checking in
    propius.end_request()

    # assign client task

    # collect client response

propius.complete_job()
propius.close()
