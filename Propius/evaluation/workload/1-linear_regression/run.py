from propius.parameter_server.config import GLOBAL_CONFIG_FILE
from propius.parameter_server.job import Propius_ps_job
from propius.parameter_server.client import Propius_ps_client
from propius.util import Client, Job
from propius.util import init, init_ps, clean_up
import yaml
import time
import torch
import matplotlib.pyplot as plt
import pandas as pd
import os

client_num = 4
clients = []
job = None
train_prop = 4 / 5

total_round = 5


def plot_cost(J_all, num_epochs):
    plt.xlabel("Epochs")
    plt.ylabel("Cost")
    plt.plot(num_epochs, J_all, "m", linewidth="5")
    plt.show()


def load_data(filename):
    df = pd.read_csv(filename, sep=",", index_col=False)
    df.fillna(0, inplace=True)
    columns_of_interest = [
        "livingArea",
        "bathrooms",
        "bedrooms",
        "favoriteCount",
        "lastSoldPrice",
        "pageViewCount",
        "price",
    ]
    extracted_data = df[columns_of_interest]
    data = torch.tensor(extracted_data.values, dtype=torch.float32)
    data = torch.hstack((torch.ones((data.shape[0], 1), dtype=torch.float32), data))
    # data = torch.hstack((torch.ones((data.shape[0], 1)), data))
    return data


def main():
    process = []
    try:
        print("\nsetting up")
        init(process)
        init_ps(process)

        gconfig = None
        with open(GLOBAL_CONFIG_FILE, "r") as gconfig:
            gconfig = yaml.load(gconfig, Loader=yaml.FullLoader)

        jm_ip = gconfig["job_manager_ip"]
        jm_port = gconfig["job_manager_port"]
        root_ps_ip = gconfig["root_ps_ip"]
        root_ps_port = gconfig["root_ps_port"]
        ps_ip = gconfig["leaf_ps_ip"]
        ps_port = gconfig["leaf_ps_port"]
        lb_ip = gconfig["load_balancer_ip"]
        lb_port = gconfig["load_balancer_port"]

        per_client_size = torch.empty(client_num).normal_(mean=100, std=10)
        per_client_size = per_client_size.int()

        print(f"Client dataset size: {per_client_size}")

        data = load_data("./datasets/house_price/portland_housing.csv")
        indices = torch.randperm(data.size(0))
        data = data[indices]

        train_size = int(data.shape[0] * train_prop)
        data_train = data[:train_size, :]
        data_test = data[train_size:, :]

        per_client_idx = [
            torch.randperm(train_size)[: per_client_size[i]] for i in range(client_num)
        ]

        for i in range(client_num):
            client_config = {
                "public_specifications": {
                    "cpu_f": 3,
                    "ram": 3,
                    "fp16_mem": 3,
                    "android_os": 3,
                },
                "private_specifications": {
                    "dataset_size_house_price": per_client_size[i],
                },
                "load_balancer_ip": lb_ip,
                "load_balancer_port": lb_port,
                "option": 0.0,
                "leaf_ps_ip": ps_ip,
                "leaf_ps_port": ps_port,
                "max_message_length": gconfig["max_message_length"],
            }
            clients.append(Client(data_train[per_client_idx[i], :], client_config))

        job_config = {
            "public_constraint": {"cpu_f": 3, "ram": 3, "fp16_mem": 3, "android_os": 3},
            "private_constraint": {
                "dataset_size_house_price": 50,
            },
            "total_round": total_round,
            "demand": client_num,
            "job_manager_ip": jm_ip,
            "job_manager_port": jm_port,
            "ip": "localhost",
            "port": 6000,
            "root_ps_ip": root_ps_ip,
            "root_ps_port": root_ps_port,
            "max_message_length": gconfig["max_message_length"],
        }

        weights = torch.zeros((data.shape[1] - 1, 1), dtype=torch.float32)
        model = {"weights": weights}
        job = Job(data_test, model, job_config)

        # Begin
        job.register()

        test_cost_list = []

        for i in range(total_round):
            job.request()

            for client in clients:
                client.get()
                client.execute()
                client.push()

            job.update()
            print(f"Round {i} #######")
            print(job.model["weights"])

            test_cost = job.test()
            print(f"test_cost: {test_cost}")
            test_cost_list.append(test_cost)

        job.complete()

    except Exception as e:
        print(e)
    finally:
        print("\ntearing down")
        clean_up(process)
        if test_cost_list:
            plot_cost(test_cost_list, range(total_round))


if __name__ == "__main__":

    main()
