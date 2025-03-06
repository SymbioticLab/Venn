from abc import abstractmethod
from propius.controller.util import Msg_level, Propius_logger
from propius.controller.scheduler.sc_monitor import SC_monitor
from propius.controller.scheduler.sc_db_portal import (
    SC_client_db_portal,
    SC_job_db_portal,
)
from propius.controller.channels import propius_pb2_grpc
from propius.controller.channels import propius_pb2
from propius.controller.util.commons import Job_group
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
                sched_alg
                irs_epsilon (apply to IRS algorithm)
                standard_round_time: default round execution time for SRTF
                job_public_constraint: name for constraint
                job_db_ip
                job_db_port
                sched_alg
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

        self.job_group = Job_group()
        self.lock = asyncio.Lock()

    @abstractmethod
    async def offline(self):
        pass

    @abstractmethod
    async def job_regist(self, job_id: int):
        pass

    @abstractmethod
    async def job_request(self, job_id: int):
        pass

    async def GET_JOB_GROUP(self, request, context):
        """Service function that handles job group fetch request from client manager.
        """
        async with self.lock:
            await self.offline()
            self.logger.print(repr(self.job_group), Msg_level.INFO)
            return propius_pb2.group_info(group=pickle.dumps(self.job_group))

    async def JOB_REGIST(self, request, context) -> propius_pb2.ack:
        """Service function that handles job register for offline scheduler

        Args:
            request: job manager request message: job_id.id
            context:
        """
        job_id = request.id
        async with self.lock:
            await self.job_regist(job_id)
        return propius_pb2.ack(ack=True)

    async def JOB_REQUEST(self, request, context) -> propius_pb2.ack:
        """Service function that handles job request for offline scheduler

        Args:
            request: job manager request message: job_id.id
            context:
        """
        job_id = request.id
        async with self.lock:
            await self.job_request(job_id)
        return propius_pb2.ack(ack=True)

    async def HEART_BEAT(self, request, context):
        return propius_pb2.ack(ack=True)

    async def plot_routine(self):
        while True:
            self.sc_monitor.report()
            await asyncio.sleep(60)
