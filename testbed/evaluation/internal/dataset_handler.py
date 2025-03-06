# Source:
# https://github.com/SymbioticLab/FedScale/blob/master/fedscale/dataloaders/divide_data.py

import csv
from random import Random
import numpy as np
from torch.utils.data import DataLoader
from collections import defaultdict

class Partition:
    def __init__(self, data, index):
        self.data = data
        self.index = index

    def __len__(self):
        return len(self.index)
    
    def __getitem__(self, index):
        data_idx = self.index[index]
        return self.data[data_idx]
        
class Data_partitioner:
    def __init__(self, data, num_of_labels=0, seed=1):
        self.partitions = []
        self.rng = Random()
        self.rng.seed(seed)

        self.data = data
        self.labels = self.data.targets
        np.random.seed(seed)

        self.data_len = len(self.data)
        self.num_of_labels = num_of_labels
        self.client_label_cnt = defaultdict(set)

    def get_num_of_labels(self):
        return self.num_of_labels
    
    def get_data_len(self):
        return self.data_len
    
    def get_client_len(self):
        return len(self.partitions)
    
    def get_client_label_len(self):
        return [len(self.client_label_cnt[i]) for i in range(self.get_client_len)]
    
    def trace_partition(self, data_map_file):
        """Read data mapping from data_map_file. Format: <client_id, sample_name, sample_category, category_id>"""
        print(f"Partitioning data by profile {data_map_file}...")
        client_id_maps = {}
        unqiue_client_ids = {}
        
        with open(data_map_file) as csv_file:
            csv_reader = csv.reader(csv_file, delimiter=',')
            read_first = True
            sample_id = 0

            for row in csv_reader:
                if read_first:
                    print(f'Trace names are {", ".join(row)}')
                    read_first = False
                else:
                    client_id = row[0]
                    
                    if client_id not in unqiue_client_ids:
                        unqiue_client_ids[client_id] = len(unqiue_client_ids)
                    
                    client_id_maps[sample_id] = unqiue_client_ids[client_id]
                    self.client_label_cnt[unqiue_client_ids[client_id]].add
                    (row[-1])
                    sample_id += 1

        self.partitions = [[] for _ in range(len(unqiue_client_ids))]
        for idx in range(sample_id):
            self.partitions[client_id_maps[idx]].append(idx)

    def uniform_partition(self, num_clients):
        num_of_labels = self.get_num_of_labels()
        data_len = self.get_data_len()
        indexes = list(range(data_len))
        self.rng.shuffle(indexes)
        part_len = int(1./num_clients * data_len)

        for _ in range(num_clients):
            self.partitions.append(indexes[0:part_len])
            indexes = indexes[part_len:]
    
    def partition_data_helper(self, num_clients, data_map_file=None):
        if data_map_file is not None:
            self.trace_partition(data_map_file)
        else:
            self.uniform_partition(num_clients=num_clients)
    
    def use(self, client_id, is_test, test_ratio=0):
        idx_list = self.partitions[client_id % len(self.partitions)]

        if not is_test:
            execute_length = len(idx_list)
        else:
            execute_length = int(len(idx_list) * test_ratio)

        idx_list = idx_list[:execute_length]
        self.rng.shuffle(idx_list)

        return Partition(self.data, idx_list)
    
    def get_size(self):
        return {'size': [len(partition) for partition in self.partitions]}
    
def select_dataset(client_id: int, partition: Partition, batch_size: int, args: dict, is_test: bool=False):
    if is_test:
        partition = partition.use(client_id, is_test, args['test_ratio'])

    else:
        partition = partition.use(client_id, is_test)

    drop_last = False if is_test else True

    if is_test:
        num_loaders = 0
    else:
        num_loaders = min(int(len(partition)/batch_size/2), args['num_loaders'])

    if num_loaders == 0:
        time_out = 0
    else:
        time_out = 60

    if len(partition) < batch_size and not is_test:
        raise ValueError(f"Client dataset size too small: {len(partition)}")

    return DataLoader(partition, batch_size=batch_size, shuffle=True,
                      pin_memory=True, timeout=time_out, num_workers=num_loaders, drop_last=drop_last) 