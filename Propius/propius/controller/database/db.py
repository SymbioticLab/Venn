import redis
from redis.commands.search.field import TextField, NumericField, Field
from redis.commands.search.indexDefinition import IndexDefinition, IndexType
import time
from propius.controller.util import Propius_logger, Msg_level


class Job_db:
    def __init__(self, gconfig, is_jm: bool, logger: Propius_logger):
        """Initialize job db portal

        Args:
            gconfig: config dictionary
                job_db_ip
                job_db_port
                sched_alg
                job_public_constraint: name of public constraint
                job_private_constraint: name of private constraint
                job_expire_time:
            is_jm: a bool indicating whether the user of the database is job manager
            logger
        """
        if gconfig["use_docker"]:
            host = "job_db"
        else:
            host = gconfig["job_db_ip"]
        port = int(gconfig["job_db_port"])
        self.r = redis.Redis(host=host, port=port)
        self.sched_alg = gconfig["sched_alg"]
        self.gconfig = gconfig
        self.public_constraint_name = gconfig["job_public_constraint"]
        self.private_constraint_name = gconfig["job_private_constraint"]
        self.logger = logger

        if is_jm:
            self.job_exp_time = gconfig["job_expire_time"]
            schema = (
                NumericField("$.job.timestamp", as_name="timestamp"),
                # job register time
                NumericField("$.job.total_sched", as_name="total_sched"),
                # total amount of sched time
                NumericField("$.job.start_sched", as_name="start_sched"),
                # last start scheduling time
                TextField("$.job.ip", as_name="ip"),
                NumericField("$.job.port", as_name="port"),
                NumericField("$.job.total_demand", as_name="total_demand"),
                NumericField("$.job.total_round", as_name="total_round"),
                NumericField("$.job.attained_service", as_name="attained_service"),
                NumericField("$.job.round", as_name="round"),
                NumericField("$.job.demand", as_name="demand"),
                NumericField("$.job.amount", as_name="amount"),
                NumericField("$.job.score", as_name="score"),
            )

            schema = schema + tuple(
                [
                    NumericField(f"$.job.public_constraint.{name}", as_name=name)
                    for name in self.public_constraint_name
                ]
            )

            schema = schema + tuple(
                [
                    NumericField(f"$.job.private_constraint.{name}", as_name=name)
                    for name in self.private_constraint_name
                ]
            )

            try:
                self.flushdb()
                self.r.ft("job").create_index(
                    schema,
                    definition=IndexDefinition(
                        prefix=["job:"], index_type=IndexType.JSON
                    ),
                )
            except Exception as e:
                self.logger.print(e, Msg_level.ERROR)

    def flushdb(self):
        try:
            self.r.flushdb()
        except Exception as e:
            self.logger.print(e, Msg_level.ERROR)

    def get_field(self, job_id: int, field: str):
        """Get field value

        Args:
            job_id: job id
            field: field name
        Returns:
            value for the field in db
        """
        try:
            qid = f"job:{job_id}"
            return self.r.json().get(qid, f"$.job.{field}")[0]
        except Exception as e:
            self.logger.print(e, Msg_level.ERROR)

    def exist(self, job_id: int) -> bool:
        """Check job status

        Args:
            job_id: job_id
        Returns:
            a boolean indicating whether the job exists
        """
        try:
            qid = f"job:{job_id}"
            return self.r.json().execute_command("EXISTS", qid)
        except Exception as e:
            self.logger.print(e, Msg_level.ERROR)

    def get_job_size(self) -> int:
        info = self.r.ft("job").info()
        return int(info["num_docs"])

    def get_job_constraints(self, job_id: int) -> tuple:
        """Get job constraint values of the job in a tuple

        Args:
            job_id: id of job
        """

        id = f"job:{job_id}"
        constraint_list = []
        try:
            for name in self.public_constraint_name:
                constraint_list.append(
                    float(self.r.json().get(id, f"$.job.public_constraint.{name}")[0])
                )
            return tuple(constraint_list)
        except Exception as e:
            self.logger.print(e, Msg_level.ERROR)
            return None

    def remove_job(self, job_id: int) -> tuple[tuple, int, int, float, float]:
        """Remove the job from database.
        Returns a tuple of public constraints, demand, round_executed,
        runtime and avg scheduling latency for analsis

        Args:
            job_id

        Returns:
            public_constraints
            demand: round demand
            round_executed: number of round executed
            runtime: time lapse since register
            avg_scheduling_latency
        """

        with self.r.json().pipeline() as pipe:
            while True:
                try:
                    id = f"job:{job_id}"
                    pipe.watch(id)
                    start_time = float(self.r.json().get(id, "$.job.timestamp")[0])
                    total_sched = float(self.r.json().get(id, "$.job.total_sched")[0])
                    round = int(self.r.json().get(id, "$.job.round")[0])
                    demand = int(self.r.json().get(id, "$.job.demand")[0])

                    constraint_list = []
                    for name in self.public_constraint_name:
                        constraint_list.append(
                            float(
                                self.r.json().get(
                                    id, f"$.job.public_constraint.{name}"
                                )[0]
                            )
                        )
                    for name in self.private_constraint_name:
                        constraint_list.append(
                            float(
                                self.r.json().get(
                                    id, f"$.job.private_constraint.{name}"
                                )[0]
                            )
                        )

                    runtime = time.time() - start_time
                    sched_latency = total_sched / round if round > 0 else -1
                    pipe.delete(id)
                    pipe.unwatch()
                    self.logger.print(f"Remove job:{job_id}", Msg_level.WARNING)
                    return (
                        tuple(constraint_list),
                        demand,
                        round,
                        runtime,
                        sched_latency,
                    )
                except redis.WatchError:
                    pass
                except Exception as e:
                    self.logger.print(e, Msg_level.ERROR)
                    return (None, None, None, None, None)


class Client_db:
    def __init__(
        self,
        gconfig,
        cm_id: int,
        is_cm: bool,
        logger: Propius_logger,
        flush: bool = False,
    ):
        """Initialize client db portal

        Args:
            gconfig: config dictionary
                client_manager: list of client manager address
                    ip:
                    client_db_port
                client_expire_time: expiration time of clients in the db
                job_public_constraint: name of public constraint
                flush: whether to flush the db first

            cm_id: id of the client manager is the user is client manager
            is_cm: bool indicating whether the user is client manager
            logger
        """
        if gconfig["use_docker"]:
            host = f"client_db_{cm_id}"
        else:
            host = gconfig["client_manager"][cm_id]["ip"]
        port = gconfig["client_manager"][cm_id]["client_db_port"]
        self.logger = logger
        self.r = redis.Redis(host=host, port=port)

        self.start_time = int(time.time())
        self.client_exp_time = int(gconfig["client_expire_time"])

        self.public_constraint_name = gconfig["job_public_constraint"]

        if is_cm:
            schema = (NumericField("$.client.timestamp", as_name="timestamp"),)

            schema = schema + tuple(
                [
                    NumericField(f"$.client.{name}", as_name=name)
                    for name in self.public_constraint_name
                ]
            )

            try:
                if flush:
                    self.flushdb()
                self.r.ft("client").create_index(
                    schema,
                    definition=IndexDefinition(
                        prefix=["client:"], index_type=IndexType.JSON
                    ),
                )
            except Exception as e:
                self.logger.print(e, Msg_level.ERROR)

    def flushdb(self):
        self.r.flushdb()


class Temp_client_db:
    def __init__(
        self,
        gconfig,
        cm_id: int,
        is_cm: bool,
        logger: Propius_logger,
        flush: bool = False,
    ):
        """Initialize temp client db portal.

        Temp client db is to store ready-to-be-assigned clients

        Args:
            gconfig: config dictionary
                client_manager: list of client manager address
                    ip:
                    client_db_port
                client_expire_time: expiration time of clients in the db
                job_public_constraint: name of public constraint
                flush: whether to flush the db first

            cm_id: id of the client manager is the user is client manager
            is_cm: bool indicating whether the user is client manager
            logger
        """
        if gconfig["use_docker"]:
            host = f"client_db_{cm_id}"
        else:
            host = gconfig["client_manager"][cm_id]["ip"]
        port = gconfig["client_manager"][cm_id]["client_db_port"]
        self.logger = logger
        self.r = redis.Redis(host=host, port=port)
        self.start_time = int(time.time())
        self.client_exp_time = 30

        self.public_constraint_name = gconfig["job_public_constraint"]
        self.public_max = gconfig["public_max"]

        if is_cm:
            schema = (
                TextField("$.temp.job_ids", as_name="job_ids"),
                NumericField("$.temp.option", as_name="option"),
            )

            schema = schema + tuple(
                [
                    NumericField(f"$.temp.{name}", as_name=name)
                    for name in self.public_constraint_name
                ]
            )

            try:
                if flush:
                    self.flushdb()
                self.r.ft("temp").create_index(
                    schema,
                    definition=IndexDefinition(
                        prefix=["temp:"], index_type=IndexType.JSON
                    ),
                )
            except Exception as e:
                self.logger.print(e, Msg_level.ERROR)

    def flushdb(self):
        self.r.flushdb()
