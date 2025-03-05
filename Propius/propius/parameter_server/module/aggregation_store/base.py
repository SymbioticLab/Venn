"""Aggregation store base module."""

from propius.parameter_server.module.commons import Entry
from propius.parameter_server.module.reduce import base_reduce
import copy
import asyncio
import torch


class Aggregation_store_entry(Entry):
    def __init__(self, in_memory: bool = True):
        super().__init__(in_memory)
        self.agg_cnt = 0
        self.ttl = 1000

    def __str__(self):
        return super().__str__() + f", agg_cnt: {self.agg_cnt}, ttl: {self.ttl}"

    def increment_agg_cnt(self, cnt: int):
        self.agg_cnt += copy.deepcopy(cnt)

    def get_agg_cnt(self):
        return self.agg_cnt

    def set_ttl(self, ttl: int):
        self.ttl = copy.deepcopy(ttl)

    def decrement_ttl(self) -> int:
        self.ttl -= 1
        return self.get_ttl()

    def get_ttl(self) -> int:
        return self.ttl


class Aggregation_store:
    def __init__(self):
        self.store_dict = {}
        self.lock = asyncio.Lock()

    async def get_key(self):
        async with self.lock:
            return list(self.store_dict.keys())

    async def set_entry(self, job_id: int, entry: Aggregation_store_entry):
        async with self.lock:
            self.store_dict[job_id] = entry

    async def get_entry(self, job_id: int):
        async with self.lock:
            return copy.deepcopy(self.store_dict.get(job_id))

    async def clear_entry(self, job_id: int):
        async with self.lock:
            entry: Aggregation_store_entry = self.store_dict.pop(job_id, None)
            if entry:
                entry.clear()

    async def update(
        self, job_id: int, round: int, agg_cnt: int, data, meta={}
    ) -> bool:
        pass

    def __str__(self):
        s = ""
        for key, entry in self.store_dict.items():
            s += f"job_id: {key}, " + entry.__str__() + "\n"
        return s
