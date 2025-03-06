"""FIFO scheduler"""

from propius.controller.util import Propius_logger, Msg_level
from propius.controller.scheduler.offline_module.base_scheduler import Scheduler
from propius.controller.channels import propius_pb2

class FIFO_scheduler(Scheduler):
    def __init__(self, gconfig: dict, logger: Propius_logger):
        super().__init__(gconfig, logger)
        # only one group
        self.job_group.insert_key(0)
        q = ""
        for name in self.public_constraint_name:
            q += f"@{name}: [-inf +inf] "
        self.job_group[0].insert_condition_and(q)

    async def job_regist(self, job_id: int):
        job_list = self.job_group.get_job_group(0)
        updated_job_list = list(filter(lambda x: self.job_db_portal.exist(x), job_list))
        updated_job_list.append(job_id)
        self.job_group.set_job_group(0, updated_job_list)

    async def job_request(self, job_id: int):
        pass

    async def offline(self):
        pass
