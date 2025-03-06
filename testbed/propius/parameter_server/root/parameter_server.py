"""Root parameter server."""

from propius.parameter_server.util import Msg_level, Propius_logger
from propius.parameter_server.module.parameter_store.base import (
    Parameter_store_entry,
    Parameter_store,
)
from propius.parameter_server.module.aggregation_store.root import (
    Root_aggregation_store_entry,
    Root_aggregation_store,
)
import pickle
from propius.parameter_server.channels import parameter_server_pb2
from propius.parameter_server.channels import parameter_server_pb2_grpc
import asyncio


class Parameter_server:
    def __init__(self, gconfig, logger):
        self.aggregation_store = Root_aggregation_store(
            gconfig["root_aggregation_store_ttl"]
        )
        self.parameter_store = Parameter_store(gconfig["root_parameter_store_ttl"])

        self.gconfig = gconfig
        self.logger: Propius_logger = logger

    async def CLIENT_GET(self, request, context):
        """Handler for client get request."""
        job_id, round = request.job_id, request.round
        self.logger.print(
            f"receive client GET request, job_id: {job_id}, round: {round}",
            Msg_level.INFO,
        )

        entry: Parameter_store_entry = await self.parameter_store.get_entry(job_id)

        return_msg = parameter_server_pb2.job(
            code=3,
            job_id=-1,
            round=-1,
            meta=pickle.dumps({}),
            data=pickle.dumps([]),
        )
        if entry:
            entry_round = entry.get_round()
            if entry_round == round:
                self.logger.print(entry, Msg_level.INFO)
                # self.logger.print(entry.get_param(), Msg_level.INFO)

                return_msg = parameter_server_pb2.job(
                    code=1,
                    job_id=job_id,
                    round=entry_round,
                    meta=pickle.dumps({}),
                    data=entry.get_param(),
                )
            elif entry_round < round:
                self.logger.print(
                    f"job: {job_id} stale round {entry_round}, {round} expected"
                )
                return_msg = parameter_server_pb2.job(
                    code=2,
                    job_id=job_id,
                    round=entry_round,
                    meta=pickle.dumps({}),
                    data=pickle.dumps([]),
                )
        return return_msg

    async def JOB_PUT(self, request, context):
        """Handler for new job round, remove old entry in both store, and set new one."""

        job_id, round = request.job_id, request.round
        meta: dict = pickle.loads(request.meta)
        data = request.data
        self.logger.print(
            f"receive job PUT request, job_id: {job_id}, round: {round}", Msg_level.INFO
        )
        await self.aggregation_store.clear_entry(job_id)
        await self.parameter_store.clear_entry(job_id)

        new_entry = Parameter_store_entry(in_memory=self.gconfig["in_memory"])
        new_entry.set_config({})
        new_entry.set_param(data)
        new_entry.set_round(round)
        await self.parameter_store.set_entry(job_id, new_entry)

        new_agg_entry = Root_aggregation_store_entry(in_memory=self.gconfig["in_memory"])
        new_agg_entry.set_config({})
        new_agg_entry.set_demand(meta["demand"])
        new_agg_entry.set_round(round)
        await self.aggregation_store.set_entry(job_id, new_agg_entry)

        return_msg = parameter_server_pb2.ack(code=1)
        return return_msg

    async def CLIENT_PUSH(self, request, context):
        """Handler for round updates, only accept when aggregation store has corresponding entry."""

        job_id, round = request.job_id, request.round
        meta = pickle.loads(request.meta)
        data = request.data
        self.logger.print(
            f"receive client PUSH request, job_id: {job_id}, round: {round}",
            Msg_level.INFO,
        )

        result = await self.aggregation_store.update(
            job_id, round, meta["agg_cnt"], data
        )
        if result:
            return parameter_server_pb2.ack(code=1)
        else:
            return parameter_server_pb2.ack(code=4)

    async def JOB_GET(self, request, context):
        """Handler of job GET request for aggregation result."""

        job_id, round = request.job_id, request.round

        self.logger.print(
            f"receive job GET request, job_id: {job_id}, round: {round}", Msg_level.INFO
        )

        entry: Root_aggregation_store_entry = await self.aggregation_store.get_entry(
            job_id
        )

        return_msg = parameter_server_pb2.job(
            code=3,
            job_id=-1,
            round=-1,
            meta=pickle.dumps({}),
            data=pickle.dumps([]),
        )
        if entry and round == entry.get_round():
            if entry.get_demand() <= entry.get_agg_cnt():
                self.logger.print(entry, Msg_level.INFO)
                return_msg = parameter_server_pb2.job(
                    code=1,
                    job_id=job_id,
                    round=round,
                    meta=pickle.dumps({}),
                    data=entry.get_param(),
                )
            else:
                self.logger.print(
                    f"parameter pending status, current: {entry.get_agg_cnt()}, expected: {entry.get_demand()}",
                    Msg_level.INFO,
                )
                return_msg = parameter_server_pb2.job(
                    code=6,
                    job_id=job_id,
                    round=round,
                    meta=pickle.dumps({}),
                    data=pickle.dumps([]),
                )
        return return_msg

    async def JOB_DELETE(self, request, context):
        """Handler for job deletion request."""

        job_id = request.job_id
        self.logger.print(
            f"receive job DELETE request, job_id: {job_id}",
            Msg_level.INFO,
        )
        await self.parameter_store.clear_entry(job_id)
        await self.aggregation_store.clear_entry(job_id)

        return parameter_server_pb2.ack(code=1)

    async def clock_evict_routine(self):
        ps_routine = asyncio.create_task(self.parameter_store.clock_evict_routine())
        agg_routine = asyncio.create_task(self.aggregation_store.clock_evict_routine())

        try:
            await asyncio.gather(ps_routine, agg_routine)
        except asyncio.CancelledError:
            pass
