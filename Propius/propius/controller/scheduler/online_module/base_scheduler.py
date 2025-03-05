"""Job base scheduler class."""

from abc import abstractmethod
from propius.controller.util import Msg_level, Propius_logger
from propius.controller.scheduler.sc_monitor import SC_monitor
from propius.controller.scheduler.sc_db_portal import (
    SC_client_db_portal,
    SC_job_db_portal,
)
from propius.controller.channels import propius_pb2_grpc
from propius.controller.channels import propius_pb2
import pickle
import asyncio
import time


class Scheduler(propius_pb2_grpc.SchedulerServicer):
    def __init__(self, gconfig: dict, logger: Propius_logger):
        """Init scheduler class

        Args:
            gconfig global config dictionary
                scheduler_ip
                scheduler_port
                irs_epsilon (apply to IRS algorithm)
                standard_round_time: default round execution time for SRTF
                job_public_constraint: name for constraint
                job_db_ip
                job_db_port
                job_public_constraint: name of public constraint
                job_private_constraint: name of private constraint
                public_max: upper bound of the score
                job_expire_time
                client_manager: list of client manager address
                    ip:
                    client_db_port
                client_expire_time: expiration time of clients in the db
            logger
        """

        self.ip = gconfig["scheduler_ip"] if not gconfig["use_docker"] else "0.0.0.0"
        self.port = gconfig["scheduler_port"]

        self.job_db_portal = SC_job_db_portal(gconfig, logger)
        self.client_db_portal = SC_client_db_portal(gconfig, logger)

        self.public_max = gconfig["public_max"]

        self.public_constraint_name = gconfig["job_public_constraint"]

        self.sc_monitor = SC_monitor(
            logger, gconfig["plot_path"], gconfig["plot"]
        )
        self.logger = logger

        self.start_time = time.time()

    @abstractmethod
    async def online(self, job_id: int, is_regist: bool):
        pass

    async def JOB_REGIST(self, request, context) -> propius_pb2.ack:
        """Service function that handles job register for online scheduler

        Args:
            request: job manager request message: job_id.id
            context:
        """
        job_id = request.id
        await self.sc_monitor.request(job_id)
        self.logger.print("receive job register", Msg_level.INFO)
        await self.online(job_id, True)
        return propius_pb2.ack(ack=True)

    async def JOB_REQUEST(self, request, context) -> propius_pb2.ack:
        """Service function that handles new job request for online scheduler

        Args:
            request: job manager request message: job_id.id
            context:
        """
        job_id = request.id
        await self.sc_monitor.request(job_id)
        self.logger.print("receive job request", Msg_level.INFO)
        await self.online(job_id, False)
        return propius_pb2.ack(ack=True)

    async def HEART_BEAT(self, request, context):
        return propius_pb2.ack(ack=True)

    async def plot_routine(self):
        while True:
            self.sc_monitor.report()
            await asyncio.sleep(60)

        # if self.sched_alg == "irs":
        #     # Update every job score using IRS
        #     await self._irs_score(job_id)
        # elif self.sched_alg == "irs2":
        #     # Update every job socre using IRS with a slight tweek that has experimental
        #     # performance improvement
        #     await self._irs2_score(job_id)

        # elif self.sched_alg == "irs3":
        #     # Update every job score using IRS
        #     self.job_group_manager.update_job_group(job_id != -1, job_id)

        # elif self.sched_alg == "srtf":
        #     # Give every job a score of -remaining time
        #     # remaining time = past avg round time * remaining round
        #     # Prioritize job with the shortest remaining demand
        #     self.job_db_portal.srtf_update_all_job_score(self.std_round_time)

        # elif self.sched_alg == "las":
        #     # Give every job a score of -attained service
        #     self.job_db_portal.las_update_all_job_score()
