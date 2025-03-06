"""SRSF scheduler."""

from propius.controller.scheduler.online_module.base_scheduler import Scheduler
from propius.controller.util import Msg_level, Propius_logger
import random


class SRSF_scheduler(Scheduler):
    def __init__(self, gconfig: dict, logger: Propius_logger):
        super().__init__(gconfig, logger)

    async def online(self, job_id: int, is_regist: bool):
        """Give every job a score of -remaining demand

            remaining demand = demand - attained amount
            Prioritize job with the smallest remaining demand.

        Args:
            job_id: job id
            is_regist: boolean indicating whether this job just registers
        """
        if not is_regist:
            demand = int(self.job_db_portal.get_field(job_id, "demand"))
            amount = int(self.job_db_portal.get_field(job_id, "amount"))

            remain_demand = max(demand - amount, 0)
            score = -remain_demand
            self.job_db_portal.set_score(score, job_id)
