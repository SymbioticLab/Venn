# -*- coding: utf-8 -*-
import csv
import logging
import random
import time
from collections import defaultdict
from random import Random

import numpy as np
from torch.utils.data import DataLoader

class Partition(object):
    """ Dataset partitioning helper """

    def __init__(self, data, index):
        self.data = data
        self.index = index

    def __len__(self):
        return len(self.index)
    
    def __getitem__(self, index):
        data_idx = self.index[index]
        return self.data[data_idx]
    

class DataPartitioner(object):
    """Partition data by trace or random"""

    def __init__(self, data, args, numOfClass=0, seed=10, isTest=False):
        self.partitions = []
        self.rng = Random()
        self.rng.seed(seed)

        self.data = data
        self.labels = self.data.targets
        self.args = args
        self.isTest = isTest
        np.random.seed(seed)

        self.data_len = len(self.data)
        self.numOfLabels = numOfClass
        self.client_label_cnt = defaultdict(set)

    def getNumOfLabels(self):
        return self.numOfLabels
    
    def getDataLen(self):
        return self.data_len
    
    def getClientLen(self):
        return len(self.partitions)
    
    def getClientLable(self):
        return [len(self.client_label_cnt[i]) for i in range(self.getClientLen())]
    
    def trace_partition(self, data_map_file):
        """Read data mapping from data_map_file. Format: <client_id, sample_name, sample_category, category_id>"""
        logging.info(f"Partitioning data by profile {data_map_file}...")
        print(f"Partitioning data by profile {data_map_file}...")
        client_id_maps = {}
        unique_client_ids = {}
        # load meta data from the data_map_file
        with open(data_map_file) as csv_file:
            csv_reader = csv.reader(csv_file, delimiter=',')
            read_first = True
            sample_id = 0

            for row in csv_reader:
                if read_first:
                    logging.info(f'Trace names are {", ".join(row)}')
                    print(f'Trace names are {", ".join(row)}')
                    read_first = False
                else:
                    client_id = row[0]

                    if client_id not in unique_client_ids:
                        unique_client_ids[client_id] = len(unique_client_ids)
                    
                    client_id_maps[sample_id] = unique_client_ids[client_id]
                    self.client_label_cnt[unique_client_ids[client_id]].add(row[-1])
                    sample_id += 1

        # Partition data given mapping
        self.partitions = [[] for _ in range(len(unique_client_ids))]

        for idx in range(sample_id):
            self.partitions[client_id_maps[idx]].append(idx)

    def partition_data_helper(self, num_clients, data_map_file=None):
        # read mapping file to partition trace
        if data_map_file is not None:
            self.trace_partition(data_map_file)
        else:
            self.uniform_partition(num_clients=num_clients)

    def uniform_partition(self, num_clients):
        # random
        numOfLabels = self.getNumOfLabels()
        data_len = self.getDataLen()
        logging.info(f"Randomly partitioning data, {data_len} samples...")

        indexes = list(range(data_len))
        self.rng.shuffle(indexes)
        part_len = int(1./num_clients * data_len)
        
        for _ in range(num_clients):
            self.partitions.append(indexes[0:part_len])
            indexes = indexes[part_len:]
    
    def use(self, partition, istest, test_ratio=0):
        resultIndex = self.partitions[partition % len(self.partitions)]

        if not istest:
            executeLength = len(resultIndex)
        else:
            executeLength = int(len(resultIndex) * test_ratio)
        
        resultIndex = resultIndex[:executeLength]
        self.rng.shuffle(resultIndex)

        return Partition(self.data, resultIndex)
    
    def getSize(self):
        # return the size of samples
        return {'size': [len(partition) for partition in self.partitions]}
    

def select_dataset(rank, partition, batch_size, args, isTest=False, collate_fn=None):
    """Load data given client Id"""
    if isTest:
        partition = partition.use(rank - 1, isTest, args.test_ratio)
    else:
        partition = partition.use(rank - 1, isTest)
    dropLast = False if isTest else True
    if isTest:
        num_loaders = 0
    else:
        num_loaders = min(int(len(partition)/batch_size/2), args.num_loaders)
    if num_loaders == 0:
        time_out = 0
    else:
        time_out = 60

    if collate_fn is not None:
        return DataLoader(partition, batch_size=batch_size, shuffle=True, pin_memory=True,
                          timeout=time_out, num_workers=num_loaders, drop_last=dropLast, collate_fn=collate_fn)
    
    return DataLoader(partition, batch_size=batch_size, shuffle=True, pin_memory=True,
                      timeout=time_out, num_workers=num_loaders, drop_last=dropLast)



    

