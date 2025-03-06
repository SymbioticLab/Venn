from propius.controller.channels import propius_pb2_grpc
from propius.controller.channels import propius_pb2
import pickle
import grpc
import time
import asyncio
from datetime import datetime
import logging
import math
from propius.controller.util.commons import *
from propius.controller.job.propius_job import Propius_job
import gc


class Propius_job_aio(Propius_job):
    async def _cleanup_routine(self):
        try:
            await self._jm_channel.close()
        except Exception:
            pass

    def _connect_jm(self) -> None:
        try:
            self._jm_channel = None
            self._jm_stub = None
            gc.collect()
        except Exception as e:
            self._custom_print(e, Msg_level.ERROR)

        self._jm_channel = grpc.aio.insecure_channel(f"{self._jm_ip}:{self._jm_port}")
        self._jm_stub = propius_pb2_grpc.Job_managerStub(self._jm_channel)

        self._custom_print(
            f"Job: connecting to job manager at {self._jm_ip}:{self._jm_port}",
            Msg_level.INFO,
        )

    async def connect(self):
        """Connect to Propius job manager

        Raise:
            RuntimeError: if can't establish connection after multiple trial
        """
        for _ in range(3):
            try:
                self._connect_jm()
                return
            except Exception as e:
                self._custom_print(e, Msg_level.ERROR)
                await asyncio.sleep(5)

        raise RuntimeError("Unable to connect to Propius job manager at the moment")

    async def close(self) -> None:
        """Clean up allocation, close connection to Propius job manager"""

        await self._cleanup_routine()
        self._custom_print(
            f"Job {self.id}: closing connection to Propius", Msg_level.INFO
        )

    async def register(self) -> bool:
        """Register job. Send job config to Propius job manager. This configuration will expire
        in one week, which means the job completion time should be within one week.

        Returns:
            ack: status of job register

        Raise:
            RuntimeError: if can't send register request after multiple trial
        """

        job_info_msg = propius_pb2.job_info(
            est_demand=int(1.1 * self.demand),
            est_total_round=self.est_total_round,
            public_constraint=pickle.dumps(self.public_constraint),
            private_constraint=pickle.dumps(self.private_constraint),
            ip=pickle.dumps(self.ip),
            port=self.port,
        )
        for _ in range(3):
            await self.connect()
            try:
                ack_msg = await self._jm_stub.JOB_REGIST(job_info_msg)
                self.id = ack_msg.id
                ack = ack_msg.ack
                await self._cleanup_routine()
                if not ack:
                    if self.verbose:
                        self._custom_print(
                            f"Job {self.id}: register failed", Msg_level.WARNING
                        )
                    return False
                else:
                    if self.verbose:
                        self._custom_print(
                            f"Job {self.id}: register success", Msg_level.INFO
                        )
                    return True
            except Exception as e:
                if self.verbose:
                    self._custom_print(e, Msg_level.ERROR)
                await self._cleanup_routine()
                await asyncio.sleep(5)

        raise RuntimeError("Unable to register to Propius job manager at the moment")

    async def start_request(self, new_demand: bool = False, demand: int = 0) -> int:
        """Send start request to Propius job manager

        Client will be routed to parameter server after this call
        until the number of clients has reached specified demand, or end_request is called.
        Note that though Propius provide the guarantee that the requested demand will be satisfied,
        allocated clients may experience various issues such as network failure
        such that the number of check-in clients might be lower than what is demanded at the parameter server

        Args:
            new_demand: boolean indicating whether to use a new demand number for this round (only)
            demand: positive integer indicating number of demand in this round.
                    If not specified, will use the default demand which is specified in the initial configuration

        Returns:
            round: an integer indicating current round, -1 for failure
        Raise:
            RuntimeError: if can't send request after multiple trial
            ValueError: if input demand is not a positive integer
        """

        if not new_demand:
            this_round_demand = self.demand
        else:
            if demand <= 0:
                raise ValueError("Input demand number is not a positive integer")
            else:
                this_round_demand = demand

        request_msg = propius_pb2.job_round_info(id=self.id, demand=this_round_demand)

        for _ in range(3):
            await self.connect()
            try:
                ack_msg = await self._jm_stub.JOB_REQUEST(request_msg)
                await self._cleanup_routine()
                if not ack_msg.ack:
                    self._custom_print(
                        f"Job {self.id}: round request failed", Msg_level.WARNING
                    )
                    return -1
                else:
                    self._custom_print(
                        f"Job {self.id}: round request succeeded", Msg_level.INFO
                    )
                    return ack_msg.round
            except Exception as e:
                self._custom_print(e, Msg_level.ERROR)
                await self._cleanup_routine()
                await asyncio.sleep(5)

        raise RuntimeError(
            "Unable to send start request to Propius job manager at the moment"
        )

    async def end_request(self) -> bool:
        """Send end request to Propius job manager. Client won't be routed to parameter server after this call,
        unless start_request is called

        Raise:
            RuntimeError: if can't send end request after multiple trial
        """

        request_msg = propius_pb2.job_id(id=self.id)

        for _ in range(3):
            await self.connect()
            try:
                ack_msg = await self._jm_stub.JOB_END_REQUEST(request_msg)
                await self._cleanup_routine()
                if not ack_msg.ack:
                    self._custom_print(
                        f"Job {self.id}: end request failed", Msg_level.WARNING
                    )
                    return False
                else:
                    self._custom_print(
                        f"Job {self.id}: end request succeeded", Msg_level.INFO
                    )
                    return True
            except Exception as e:
                self._custom_print(e, Msg_level.ERROR)
                await self._cleanup_routine()
                await asyncio.sleep(5)

        raise RuntimeError(
            "Unable to send end request to Propius job manager at this moment"
        )

    async def complete_job(self):
        """Send complete job request to Propius job manager. Job configuration will be removed from Propius.

        Raise:
            RuntimeError: if can't send complete_job request after multiple trial
        """

        req_msg = propius_pb2.job_id(id=self.id)

        for _ in range(3):
            await self.connect()
            try:
                await self._jm_stub.JOB_FINISH(req_msg)
                await self._cleanup_routine()
                self._custom_print(f"Job {self.id}: job completed", Msg_level.WARNING)
                return
            except Exception as e:
                self._custom_print(e, Msg_level.ERROR)
                await self._cleanup_routine()
                await asyncio.sleep(5)

        raise RuntimeError(
            "Unable to send complete job request to Propius job manager at this moment"
        )

    async def heartbeat(self):
        """Keep connection alive for long intervals during request"""
        await self._jm_stub.HEART_BEAT(propius_pb2.empty())
