"""FL Job Manager Class."""

from propius.controller.util import Msg_level, Propius_logger
from propius.controller.job_manager.jm_monitor import JM_monitor
from propius.controller.job_manager.jm_db_portal import JM_job_db_portal
from propius.controller.channels import propius_pb2_grpc
from propius.controller.channels import propius_pb2
import asyncio
import pickle
import grpc


class Job_manager(propius_pb2_grpc.Job_managerServicer):
    def __init__(self, gconfig: dict, logger: Propius_logger):
        """Init job manager class. Connect to scheduler server

        Args:
            gconfig: global config file
                job_manager_ip
                job_manager_port
                job_db_ip
                job_db_port
                job_public_constraint: name of public constraint
                job_private_constraint: name of private constraint
                job_expire_time
                scheduler_ip
                scheduler_port
                logger
        """
        self.gconfig = gconfig
        self.ip = gconfig["job_manager_ip"] if not gconfig["use_docker"] else "0.0.0.0"
        self.port = int(gconfig["job_manager_port"])

        self.jm_monitor = JM_monitor(logger, gconfig["plot_path"], gconfig["plot"])
        self.logger = logger

        self.job_db_portal = JM_job_db_portal(gconfig, logger)

        self.sched_channel = None
        self.sched_portal = None

        self._connect_sched(gconfig["scheduler_ip"], int(gconfig["scheduler_port"]))

        self.lock = asyncio.Lock()
        self.job_total_num = 0

    def _connect_sched(self, sched_ip: str, sched_port: int) -> None:
        if self.gconfig["use_docker"]:
            sched_ip = "scheduler"
        self.sched_channel = grpc.aio.insecure_channel(f"{sched_ip}:{sched_port}")
        self.sched_portal = propius_pb2_grpc.SchedulerStub(self.sched_channel)
        self.logger.print(
            f"connecting to scheduler at {sched_ip}:{sched_port}",
            Msg_level.INFO,
        )

    async def JOB_REGIST(self, request, context):
        """Insert job registration into database, return job_id assignment, and ack

        Args:
            request:
                job_info
        """
        est_demand = request.est_demand
        est_total_round = request.est_total_round
        job_ip, job_port = pickle.loads(request.ip), request.port
        public_constraint = pickle.loads(request.public_constraint)
        private_constraint = pickle.loads(request.private_constraint)

        job_id = self.job_total_num
        self.job_total_num += 1

        ack = self.job_db_portal.register(
            job_id=job_id,
            public_constraint=public_constraint,
            private_constraint=private_constraint,
            job_ip=job_ip,
            job_port=job_port,
            total_demand=est_demand * est_total_round
            if est_total_round > 0
            else 2 * est_demand,
            total_round=est_total_round,
        )

        self.logger.print(
            f"ack job {job_id} register: {ack}, public constraint: {public_constraint}"
            f", private constraint: {private_constraint}, demand: {est_demand}",
            Msg_level.INFO,
        )
        if ack:
            await self.jm_monitor.job_register()
            await self.sched_portal.JOB_REGIST(propius_pb2.job_id(id=job_id))

        await self.jm_monitor.request()
        return propius_pb2.job_register_ack(id=job_id, ack=ack)

    async def JOB_REQUEST(self, request, context):
        """Update job metadata based on job round request. Returns ack

        Args:
            request:
                job_round_info
        Returns:
            jm_ack:
                ack
                round
        """

        job_id, demand = request.id, request.demand
        ack, round = self.job_db_portal.request(job_id=job_id, demand=demand)

        self.job_db_portal.update_total_demand_estimate(job_id, demand)

        await self.sched_portal.JOB_REQUEST(propius_pb2.job_id(id=job_id))

        self.logger.print(
            f"ack job {job_id} round request: {ack}", Msg_level.INFO
        )

        await self.jm_monitor.request()
        return propius_pb2.jm_ack(ack=ack, round=round)

    async def JOB_END_REQUEST(self, request, context):
        """Update job metadata based on job round end request. Returns ack

        Args:
            request:
                job_id
        """

        job_id = request.id
        ack = self.job_db_portal.end_request(job_id=job_id)
        self.logger.print(
            f"ack job {job_id} end round request: {ack}", Msg_level.INFO
        )

        await self.jm_monitor.request()
        return propius_pb2.ack(ack=ack)

    async def JOB_FINISH(self, request, context):
        """Remove job from database

        Args:
            request:
                job_id
        """

        job_id = request.id

        (
            constraints,
            demand,
            total_round,
            runtime,
            sched_latency,
        ) = self.job_db_portal.finish(job_id)
        self.logger.print(
            f"job {job_id} completed" f", executed {total_round} rounds",
            Msg_level.INFO,
        )

        if runtime:
            await self.jm_monitor.job_finish(
                constraints, demand, total_round, runtime, sched_latency
            )
        await self.jm_monitor.request()
        return propius_pb2.empty()

    async def HEART_BEAT(self, request, context):
        return propius_pb2.ack(ack=True)

    async def plot_routine(self):
        while True:
            self.jm_monitor.report()
            await asyncio.sleep(60)

    async def heartbeat_routine(self):
        """Send heartbeat routine to scheduler and prune job db if needed."""
        try:
            while True:
                await asyncio.sleep(30)
                try:
                    await self.sched_portal.HEART_BEAT(propius_pb2.empty())
                except:
                    pass
                self.job_db_portal.prune()

        except asyncio.CancelledError:
            pass
