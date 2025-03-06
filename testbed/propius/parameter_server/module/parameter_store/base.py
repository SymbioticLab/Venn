"""Parameter store base module"""

from propius.parameter_server.module.commons import Entry
import copy
import asyncio


class Parameter_store_entry(Entry):
    def __init__(self, in_memory: bool = True):
        super().__init__(in_memory)
        self.ttl = 100

    def __str__(self):
        return super().__str__() + f", ttl: {self.ttl}"

    def set_ttl(self, ttl: int):
        self.ttl = copy.deepcopy(ttl)

    def decrement_ttl(self) -> int:
        self.ttl -= 1
        return self.get_ttl()

    def get_ttl(self) -> int:
        return self.ttl


class Parameter_store:
    def __init__(self, default_ttl=100):
        self.store_dict = {}
        self.lock = asyncio.Lock()
        self.default_ttl = default_ttl

    async def set_entry(self, job_id: int, entry: Parameter_store_entry):
        async with self.lock:
            entry.set_ttl(self.default_ttl)
            self.store_dict[job_id] = entry

    async def get_entry(self, job_id: int):
        async with self.lock:
            return copy.deepcopy(self.store_dict.get(job_id))

    async def clear_entry(self, job_id: int):
        async with self.lock:
            entry: Parameter_store_entry = self.store_dict.pop(job_id, None)
            if entry:
                entry.clear()

    async def clock_evict_routine(self):
        try:
            while True:
                async with self.lock:
                    for key in list(self.store_dict.keys()):
                        entry = self.store_dict[key]
                        ttl = entry.decrement_ttl()
                        if ttl <= 0:
                            entry.clear()
                            self.store_dict.pop(key, None)
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            pass

    def __str__(self):
        s = ""
        for key, entry in self.store_dict.items():
            s += f"job_id: {key}, " + entry.__str__() + "\n"
        return s 


