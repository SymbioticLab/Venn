"""FL Edge Device (Client) Manager Class"""

from propius.controller.util import Propius_logger, Msg_level
from propius.controller.client_manager.cm_monitor import CM_monitor
from propius.controller.client_manager.cm_db_portal import (
    CM_client_db_portal,
    CM_job_db_portal,
)
from propius.controller.channels import propius_pb2_grpc
from propius.controller.channels import propius_pb2
import pickle
import asyncio
import grpc


class Client_manager(propius_pb2_grpc.Client_managerServicer):
    def __init__(self, gconfig, cm_id: int, logger: Propius_logger):
        """Initialize client db portal

        Args:
            gconfig: config dictionary
                client_manager: list of client manager address
                    ip
                    port
                    client_db_port
                client_expire_time: expiration time of clients in the db
                client_manager_id_weight
                job_public_constraint: name of public constraint
                job_db_ip
                job_db_port
                job_public_constraint: name of public constraint
                job_private_constraint: name of private constraint

            cm_id: id of the client manager is the user is client manager
            logger
        """

        self.cm_id = cm_id
        self.ip = (
            gconfig["client_manager"][self.cm_id]["ip"]
            if not gconfig["use_docker"]
            else "0.0.0.0"
        )
        self.port = gconfig["client_manager"][self.cm_id]["port"]

        self.sched_mode = gconfig["sched_mode"]
        self.sched_alg = gconfig["sched_alg"]

        self.client_db_portal = CM_client_db_portal(gconfig, self.cm_id, logger, True)

        self.job_db_portal = CM_job_db_portal(gconfig, logger)

        if self.sched_mode == "offline":
            if self.sched_alg == "irs":
                from propius.controller.client_manager.offline_module.irs_temp_db_portal import (
                    IRS_temp_client_db_portal as Temp_client_db_portal,
                )
            else:
                from propius.controller.client_manager.offline_module.base_temp_db_portal import (
                    CM_temp_client_db_portal as Temp_client_db_portal,
                )

            self.temp_client_db_portal = Temp_client_db_portal(
                gconfig, self.cm_id, self.job_db_portal, logger, False
            )

        self.cm_monitor = CM_monitor(
            logger, gconfig["plot_path"], gconfig["plot"]
        )
        self.max_client_num = gconfig["client_manager_id_weight"]
        self.logger = logger

        self.lock = asyncio.Lock()
        self.client_num = 0

        self.gconfig = gconfig

        self.sched_channel = None
        self.sched_portal = None
        if self.sched_mode == "offline":
            self._connect_sched(gconfig["scheduler_ip"], int(gconfig["scheduler_port"]))

    def _connect_sched(self, sched_ip: str, sched_port: int) -> None:
        if self.gconfig["use_docker"]:
            sched_ip = "scheduler"
        self.sched_channel = grpc.aio.insecure_channel(f"{sched_ip}:{sched_port}")
        self.sched_portal = propius_pb2_grpc.SchedulerStub(self.sched_channel)
        self.logger.print(
            f"connecting to scheduler at {sched_ip}:{sched_port}",
            Msg_level.INFO,
        )

    async def CLIENT_CHECKIN(self, request, context):
        """Hanle client check in, store client meatadata to database, and
        return task offer list

        Args:
            public_specification: a tuple of client public specs

        Returns:
            cm_offer:
                client_id: assigned by client manager
                task_offer_list
                private_constraint
                total_job_num
        """

        async with self.lock:
            client_id = (
                self.max_client_num * self.cm_id + self.client_num % self.max_client_num
            )
            self.client_num += 1

        info = pickle.loads(request.public_specification)
        public_specification = info["ps"]
        option = info["op"]

        self.client_db_portal.insert(client_id, public_specification)

        task_offer_list, task_private_constraint, job_size = [], [], 0

        if self.sched_mode == "online":
            (
                task_offer_list,
                task_private_constraint,
                job_size,
            ) = self.job_db_portal.client_assign(public_specification)
        elif self.sched_mode == "offline":
            self.temp_client_db_portal.insert(client_id, public_specification, option)

        await self.cm_monitor.client_checkin()

        if len(task_offer_list) > 0:
            self.logger.print(
                f"client {client_id} check in, offer: {task_offer_list}",
                Msg_level.INFO,
            )

        return propius_pb2.cm_offer(
            client_id=client_id,
            task_offer=pickle.dumps(task_offer_list),
            private_constraint=pickle.dumps(task_private_constraint),
            total_job_num=job_size,
        )

    async def CLIENT_PING(self, request, context):
        """Hanle client check in, fetch client meatadata from database, and
        return task offer list. This method should be called if previous client task selection failed.

        Args:
            id

        Returns:
            cm_offer:
                client_id: assigned by client manager
                task_offer_list
                private_constraint
                total_job_num
        """

        public_specification = self.client_db_portal.get_public_spec(request.id)

        task_offer_list, task_private_constraint, job_size = [], [], 0

        if self.sched_mode == "online":
            (
                task_offer_list,
                task_private_constraint,
                job_size,
            ) = self.job_db_portal.client_assign(public_specification)
        elif self.sched_mode == "offline":
            task_offer_list = self.temp_client_db_portal.get_task_id(
                request.id, public_specification
            )

            (
                task_offer_list,
                task_private_constraint,
            ) = self.job_db_portal.get_job_private_constraint(task_offer_list)

        await self.cm_monitor.client_ping()

        if task_offer_list:
            self.logger.print(
                f"client {request.id} ping, offer: {task_offer_list}",
                Msg_level.INFO,
            )

        return propius_pb2.cm_offer(
            client_id=-1,
            task_offer=pickle.dumps(task_offer_list),
            private_constraint=pickle.dumps(task_private_constraint),
            total_job_num=job_size,
        )

    async def CLIENT_ACCEPT(self, request, context):
        """Handle client acceptance of a task, increment allocation amount of the corresponding job, if current amount is smaller than the corresponding round demand. Return job parameter server address, and ack.
        Otherwise, job allocation amount will not increased by the calling client,
        and the client fails to be assigned to this task.

        Args:
            client_id
            task_id

        Returns:
            cm_ack:
                ack
                job_ip
                job_port
                round
        """

        client_id, task_id = request.client_id, request.task_id
        result = self.job_db_portal.incr_amount(task_id)

        await self.cm_monitor.client_accept(result != None)

        if not result:
            self.logger.print(
                f"job {task_id} over-assign",
                Msg_level.WARNING,
            )
            return propius_pb2.cm_ack(ack=False, job_ip=pickle.dumps(""), job_port=-1, round=-1)

        if self.sched_mode == "offline":
            self.temp_client_db_portal.remove_client(client_id)

        self.logger.print(
            f"ack client {client_id}, job addr {result}",
            Msg_level.INFO,
        )
        return propius_pb2.cm_ack(
            ack=True, job_ip=pickle.dumps(result[0]), job_port=result[1], round=result[2]
        )

    async def client_assign_routine(self):
        if self.sched_mode == "offline":
            try:
                while True:
                    try:
                        self.logger.print(
                            f"update job group",
                            Msg_level.INFO,
                        )
                        group_info = await self.sched_portal.GET_JOB_GROUP(
                            propius_pb2.empty()
                        )
                        self.temp_client_db_portal.update_job_group(
                            pickle.loads(group_info.group)
                        )
                        self.temp_client_db_portal.client_assign()
                    except Exception as e:
                        self.logger.print(e, Msg_level.ERROR)
                    await asyncio.sleep(3)
            except asyncio.CancelledError:
                pass

    async def plot_routine(self):
        while True:
            self.cm_monitor.report(self.cm_id)
            await asyncio.sleep(60)

    async def HEART_BEAT(self, request, context):
        return propius_pb2.ack(ack=True)
