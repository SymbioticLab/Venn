"""Random scheduler."""

from propius.controller.scheduler.online_module.base_scheduler import Scheduler
from propius.controller.util import Msg_level, Propius_logger
import random


class Random_scheduler(Scheduler):
    def __init__(self, gconfig: dict, logger: Propius_logger):
        super().__init__(gconfig, logger)

    async def online(self, job_id: int, is_regist: bool):
        """Give every job which doesn't have a score yet a random score

        Args:
            job_id: job id
            is_regist: boolean indicating whether this job just registers
        """
        if is_regist:
            score = random.uniform(0.0, 10.0)
            self.job_db_portal.set_score(score, job_id)
