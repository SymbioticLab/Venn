from propius.parameter_server.config import GLOBAL_CONFIG_FILE
from propius.job import Job
from propius.client import Client
from propius.util import init, init_ps, clean_up
import yaml
import pytest
import time
import torch


@pytest.fixture
def setup_and_teardown_for_stuff():
    process = []
    print("\nsetting up")
    init(process)
    init_ps(process)
    yield
    print("\ntearing down")
    clean_up(process)


def test_integrate(setup_and_teardown_for_stuff):
    with open(GLOBAL_CONFIG_FILE, "r") as gconfig:
        gconfig = yaml.load(gconfig, Loader=yaml.FullLoader)

        jm_ip = gconfig["job_manager_ip"]
        jm_port = gconfig["job_manager_port"]
        root_ps_ip = gconfig["root_ps_ip"]
        root_ps_port = gconfig["root_ps_port"]
        ps_ip = gconfig["leaf_ps_ip"]
        ps_port = gconfig["leaf_ps_port"]

        job_config = {
            "public_constraint": {"cpu_f": 3, "ram": 3, "fp16_mem": 3, "android_os": 3},
            "private_constraint": {
                "dataset_size_dummy": 100,
            },
            "total_round": 2,
            "demand": 2,
            "job_manager_ip": jm_ip,
            "job_manager_port": jm_port,
            "ip": "localhost",
            "port": 6000,
            "root_ps_ip": root_ps_ip,
            "root_ps_port": root_ps_port,
            "max_message_length": gconfig["max_message_length"],
        }

        lb_ip = gconfig["load_balancer_ip"]
        lb_port = gconfig["load_balancer_port"]
        client_config = {
            "public_specifications": {
                "cpu_f": 3,
                "ram": 3,
                "fp16_mem": 3,
                "android_os": 3,
            },
            "private_specifications": {
                "dataset_size_dummy": 1000,
            },
            "load_balancer_ip": lb_ip,
            "load_balancer_port": lb_port,
            "option": 0.0,
            "leaf_ps_ip": ps_ip,
            "leaf_ps_port": ps_port,
            "max_message_length": gconfig["max_message_length"],
        }
        job = Job(job_config, True, False)
        client1 = Client(client_config, True, False)
        client2 = Client(client_config, True, False)

        time.sleep(1)
        assert job.register()

        assert job.request({}, [torch.ones(2, 2)])

        result = client1.get()
        assert result
        meta, data = result
        assert meta == {}
        assert torch.equal(data[0], torch.ones(2, 2))

        result2 = client2.get()
        assert result2
        meta2, data2 = result2
        assert meta2 == {}
        assert torch.equal(data2[0], torch.ones(2, 2))

        data[0] += 1
        client1.push(data)

        data2[0] += 2
        client2.push(data2)

        job_result = job.reduce()
        assert job_result
        _, aggregation = job_result

        assert torch.equal(aggregation[0], torch.ones(2, 2) * 5)

        assert job.request({}, [torch.ones(2, 2) * 2])
        result = client1.get()
        result2 = client2.get()
        assert torch.equal(result[1][0], torch.ones(2, 2) * 2)
        assert torch.equal(result2[1][0], torch.ones(2, 2) * 2)

        result[1][0] *= 0.5
        result2[1][0] *= 0.5
        client1.push(result[1])
        client2.push(result2[1])

        job_result = job.reduce()
        assert job_result
        _, aggregation = job_result
        assert torch.equal(aggregation[0], torch.ones(2, 2) * 2)

        job.complete()
