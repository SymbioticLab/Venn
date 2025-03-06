import redis
from redis.commands.json.path import Path
from redis.commands.search.query import Query
import time
import json
from propius.controller.database import Job_db, Client_db
from propius.controller.util import Msg_level, Propius_logger, geq


class CM_job_db_portal(Job_db):
    def __init__(self, gconfig, logger):
        """Initialize job db portal

        Args:
            gconfig: config dictionary
                job_db_ip
                job_db_port
                sched_alg
                job_public_constraint: name of public constraint
                job_private_constraint: name of private constraint
            is_jm: a bool indicating whether the user of the database is job manager
            logger
        """

        super().__init__(gconfig, False, logger)

    def client_assign(self, specification: tuple) -> tuple[list, list, int]:
        """Assign tasks to client with input specification

        The client public specification would satisfy returned task public constraints,
        but client private specification might not satisfy the returned task private constraints.
        The returned tasks' current allocation amount would be smaller than their respective demand.

        Args:
            specification: a tuple listing public spec values

        Returns:
            task_offer_list: list of job id, with size no greater than max_task_len
            task_private_constraint_list: list of tuple of private constraint
                                            for client local task selection
            size: total number of jobs for analytics
        """
        result = None
        try:
            qstr = ""
            for idx, name in enumerate(self.public_constraint_name):
                qstr += f"@{name}: [0 {specification[idx]}] "

            q = Query(qstr).sort_by("score", asc=False).paging(0, 100)
            result = self.r.ft("job").search(q)
        except Exception as e:
            self.logger.print(e, Msg_level.WARNING)

        if result:
            size = result.total
            open_list = []
            open_private_constraint = []

            max_task_len = self.gconfig["max_task_offer_list_len"]
            for doc in result.docs:
                if len(open_list) > max_task_len:
                    break
                job = json.loads(doc.json)
                job_id = int(doc.id.split(":")[1])
                if job["job"]["amount"] < job["job"]["demand"]:
                    open_list.append(job_id)
                    job_private_constraint = tuple(
                        [
                            job["job"]["private_constraint"][name]
                            for name in self.private_constraint_name
                        ]
                    )
                    open_private_constraint.append(job_private_constraint)

            return open_list, open_private_constraint, size

        return [], [], 0

    def get_job_private_constraint(self, job_list: list) -> tuple[list, list]:
        """Get job private constraint in task_offer_list

        The client public specification would satisfy returned task public constraints,
        but client private specification might not satisfy the returned task private constraints.
        The returned tasks' current allocation amount would be smaller than their respective demand.

        Args:
            job_list: list of job ids

        Returns:
            task_offer_list: list of job id, with size no greater than max_task_len
            task_private_constraint_list: list of tuple of private constraint
                                            for client local task selection
        """
        task_offer_list = []
        task_private_constraint = []
        max_task_len = self.gconfig["max_task_offer_list_len"]
        for job_id in job_list:
            if len(task_offer_list) > max_task_len:
                break
            id = f"job:{job_id}"

            try:
                if self.r.json().get(id, "$.job.amount"):
                    amount = int(self.r.json().get(id, "$.job.amount")[0])
                    demand = int(self.r.json().get(id, "$.job.demand")[0])
                    if amount >= demand:
                        continue
                    private_constraint = tuple(
                        float(
                            self.r.json().get(id, f"$.job.private_constraint.{name}")[0]
                        )
                        for name in self.private_constraint_name
                    )
                    task_offer_list.append(job_id)
                    task_private_constraint.append(private_constraint)

            except Exception as e:
                self.logger.print(e, Msg_level.ERROR)

        return task_offer_list, task_private_constraint

    def incr_amount(self, job_id: int) -> tuple[str, int]:
        """Increase the job allocation amount if current allocation amount is less than demand,
        and returns job parameter server address. If current allocation amount is no less than demand,
        allocation amount will not be further increased, and address will not be returned (assign abort)

        Args:
            job_id

        Returns:
            parameter_server_ip:
            parameter_server_port
            round
        """

        with self.r.json().pipeline() as pipe:
            while True:
                try:
                    id = f"job:{job_id}"
                    pipe.watch(id)
                    amount = int(self.r.json().get(id, "$.job.amount")[0])
                    if amount is None:
                        pipe.unwatch()
                        return None
                    demand = int(self.r.json().get(id, "$.job.demand")[0])
                    ip = str(self.r.json().get(id, "$.job.ip")[0])
                    port = int(self.r.json().get(id, "$.job.port")[0])
                    round = int(self.r.json().get(id, "$.job.round")[0])

                    if amount >= demand:
                        pipe.unwatch()
                        return None

                    pipe.multi()
                    if amount < demand:
                        pipe.execute_command("JSON.NUMINCRBY", id, "$.job.amount", 1)
                    if amount == demand - 1:
                        start_sched = float(
                            self.r.json().get(id, "$.job.start_sched")[0]
                        )
                        sched_time = time.time() - start_sched
                        pipe.execute_command(
                            "JSON.NUMINCRBY", id, "$.job.total_sched", sched_time
                        )
                        pipe.execute_command(
                            "JSON.NUMINCRBY", id, "$.job.attained_service", demand
                        )
                    pipe.execute()
                    return (ip, port, round)
                except redis.WatchError:
                    pass
                except Exception as e:
                    self.logger.print(e, Msg_level.ERROR)
                    return None
                
    def is_available(self, job_id) -> bool:
        """Check whether the job is still being allocated.
        
        Args:
            job_id: job_id

        Returns:
            a boolean
        """
        try:
            amount = int(self.get_field(job_id, "amount"))
            demand = int(self.get_field(job_id, "demand"))
            return amount < demand
        except Exception:
            return False


class CM_client_db_portal(Client_db):
    def __init__(
        self, gconfig, cm_id: int, logger: Propius_logger, flush: bool = False
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

        super().__init__(gconfig, cm_id, True, logger, flush)

    def insert(self, id: int, specifications: tuple):
        """Insert client metadata to database, set expiration time and start time

        Args:
            id
            specification: a tuple of public spec values
        """

        if len(specifications) != len(self.public_constraint_name):
            self.logger.print(
                "specification length does not match required", Msg_level.ERROR
            )

        client_dict = {"timestamp": int(time.time())}
        spec_dict = {
            self.public_constraint_name[i]: specifications[i]
            for i in range(len(specifications))
        }
        client_dict.update(spec_dict)
        client = {"client": client_dict}
        try:
            self.r.json().set(f"client:{id}", Path.root_path(), client)
            self.r.expire(f"client:{id}", self.client_exp_time)
        except Exception as e:
            self.logger.print(e, Msg_level.ERROR)

    def get_public_spec(self, id: int) -> tuple:
        """Get client public spec values

        Args:
            id

        Returns:
            specs: a tuple of public spec values
        """

        id = f"client:{id}"
        specs = [0] * len(self.public_constraint_name)
        try:
            for idx, name in enumerate(self.public_constraint_name):
                spec = float(self.r.json().get(id, f"$.client.{name}")[0])
                specs[idx] = spec
        except Exception as e:
            self.logger.print(e, Msg_level.ERROR)
        return tuple(specs)
