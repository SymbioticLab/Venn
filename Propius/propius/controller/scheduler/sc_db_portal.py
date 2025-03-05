from propius.controller.database.db import Job_db, Client_db
import json
import time
from redis.commands.search.query import Query
from propius.controller.util import Msg_level, Propius_logger


class SC_job_db_portal(Job_db):
    def __init__(self, gconfig: dict, logger: Propius_logger):
        """Initialize job db portal

        Args:
            gconfig: config dictionary
                job_db_ip
                job_db_port
                sched_alg
                job_public_constraint: name of public constraint
                job_private_constraint: name of private constraint
                job_expire_time
            logger
        """

        super().__init__(gconfig, False, logger)
        self.start_time = time.time()

    def get_affected_len(
        self, job_list_1: list, job_list_2: list, alloc_1: float, alloc_2: float
    ) -> int:
        """Get job list 1's affected job number by job_list_2.

        Args:
            job_list_1: the group with
        """
        group_2_queue_time = 0
        for job_id in job_list_2:
            try:
                qid = f"job:{job_id}"
                demand = int(self.r.json().get(qid, f"$.job.demand")[0])
                group_2_queue_time += demand
            except:
                pass

        group_2_queue_time /= alloc_2

        group_1_queue_time = 0
        cnt = 0
        for job_id in job_list_1:
            try:
                qid = f"job:{job_id}"
                demand = int(self.r.json().get(qid, f"$.job.demand")[0])
                group_1_queue_time += demand / alloc_1
                cnt += 1
                if group_1_queue_time > group_2_queue_time:
                    break
            except:
                pass

        return cnt

    def get_sched_resp(self, job_id: int) -> tuple:
        """Get job id total sched time and total response time.

        Args:
            job_id
        """

        id = f"job:{job_id}"
        try:
            total_sched = float(self.r.json().get(id, f"$.job.total_sched")[0])
            timestamp = float(self.r.json().get(id, f"$.job.timestamp")[0])
            total_resp = time.time() - timestamp - total_sched
            return (total_sched, total_resp)
        except Exception as e:
            self.logger.print(e, Msg_level.ERROR)
            return -1, -1

    def get_job_list(
        self, public_constraint: tuple, constraints_job_list: list
    ) -> bool:
        """Get all the jobs that has the input public constraint,
        sorted by the total demand in ascending order

        Use register time to break tie

        Args:
            public_constraint: constraint values listed in a tuple
            constraints_job_list: a list that the sorted job will be stored in
        """

        job_demand_map = {}
        job_time_map = {}
        # if constraints exist, insert as a list to dict, return true
        qstr = ""
        for idx, name in enumerate(self.public_constraint_name):
            qstr += f"@{name}: [{public_constraint[idx]}, {public_constraint[idx]}] "

        q = Query(qstr).paging(0, 100)

        try:
            result = self.r.ft("job").search(q)
            if result.total == 0:
                return False
        except Exception as e:
            self.logger.print(e, Msg_level.ERROR)
            return False

        for doc in result.docs:
            id = int(doc.id.split(":")[1])
            job_dict = json.loads(doc.json)["job"]
            job_demand = job_dict["demand"]
            job_amount = job_dict["amount"]
            if job_amount < job_demand:
                job_time_map[id] = job_dict["timestamp"]
                job_demand_map[id] = job_demand
                constraints_job_list.append(id)

        constraints_job_list.sort(key=lambda x: (job_demand_map[x], job_time_map[x]))

        return True

    # def irs_update_score(
    #     self,
    #     job_id: int,
    #     groupsize: int,
    #     idx: int,
    #     denominator: float,
    #     irs_epsilon: float = 0,
    #     std_round_time: float = 0,
    # ):
    #     """Calculate job score using IRS.

    #     Args:
    #         job: job id
    #         groupsize: number of jobs in a group with the same constraints
    #         idx: index of the job within the group list
    #         denominator: IRS score denominator, eligible client group size for the job group
    #         irs_epsilon: hyperparameter for fairness adjustment
    #         std_round_time: default round execution time for jobs that don't have history round info
    #     """

    #     score = (groupsize - idx) / denominator
    #     if irs_epsilon > 0:
    #         sjct = self._get_est_JCT(job_id, std_round_time)
    #         score = score * (self._get_job_time(job_id) / sjct) ** irs_epsilon
    #     try:
    #         self.r.execute_command("JSON.SET", f"job:{job_id}", "$.job.score", score)
    #         self.logger.print(f"-------job:{job_id} {score:.3f} ", Msg_level.INFO)
    #     except Exception as e:
    #         self.logger.print(e, Msg_level.ERROR)

    def query(self, qstr: str, num: int = 100):
        """Input query string, specifying max number of results
        Args:
            qstr: query string
            num: max number of results
        Returns:
            A result of documents
        """

        q = Query(qstr).paging(0, num)
        return self.r.ft("job").search(q)

    def set_score(self, score: float, job_id: int):
        """Set score for job

        Args:
            score: a float
            job_id: job id
        """
        try:
            self.logger.print(f"set job score: {job_id} {score:.3f} ", Msg_level.INFO)
            id = f"job:{job_id}"
            self.r.execute_command("JSON.SET", id, "$.job.score", score)
        except Exception as e:
            self.logger.print(e, Msg_level.ERROR)

    # def srtf_update_all_job_score(self, std_round_time: float):
    #     """Give every job a score of -remaining time
    #     remaining time = past avg round time * remaining round
    #     Prioritize job with the shortest remaining demand
    #     """
    #     try:
    #         q = Query("*").paging(0, 100)
    #         result = self.r.ft("job").search(q)
    #         if result.total == 0:
    #             return
    #         for doc in result.docs:
    #             id = doc.id
    #             job_dict = json.loads(doc.json)["job"]
    #             past_round = job_dict["round"]
    #             runtime = time.time() - job_dict["timestamp"]
    #             avg_round_time = (
    #                 runtime / past_round if past_round > 0 else std_round_time
    #             )

    #             if job_dict["total_round"] > 0:
    #                 remain_round = max(job_dict["total_round"] - job_dict["round"], 0)
    #                 remain_time = remain_round * avg_round_time
    #             else:
    #                 remain_time = runtime

    #             score = -remain_time
    #             self.logger.print(f"-------{id} {score:.3f} ", Msg_level.INFO)
    #             self.r.execute_command("JSON.SET", id, "$.job.score", score)
    #     except Exception as e:
    #         self.logger.print(e, Msg_level.ERROR)

    # def las_update_all_job_score(self):
    #     """Give every job a score of -attained service."""
    #     try:
    #         q = Query("*").paging(0, 100)
    #         result = self.r.ft("job").search(q)
    #         if result.total == 0:
    #             return
    #         for doc in result.docs:
    #             id = doc.id
    #             job_dict = json.loads(doc.json)["job"]
    #             attained_service = job_dict["attained_service"]
    #             score = -attained_service
    #             self.logger.print(f"-------{id} {score:.3f} ", Msg_level.INFO)
    #             self.r.execute_command("JSON.SET", id, "$.job.score", score)
    #     except Exception as e:
    #         self.logger.print(e, Msg_level.ERROR)

    def _get_job_time(self, job_id: int) -> float:
        id = f"job:{job_id}"
        try:
            timestamp = float(self.r.json().get(id, "$.job.timestamp")[0])
            return time.time() - timestamp
        except Exception as e:
            self.logger.print(e, Msg_level.WARNING)
            return 0

    def _get_est_JCT(self, job_id: int, std_round_time: float) -> float:
        id = f"job:{job_id}"
        try:
            start_time = float(self.r.json().get(job_id, "$.job.timestamp")[0])
            round_executed = int(self.r.json().get(job_id, "$.job.round")[0])
            runtime = time.time() - start_time
            avg_round_time = (
                runtime / round_executed if round_executed > 0 else std_round_time
            )

            total_round = int(self.r.json().get(id, ".job.total_round")[0])
            if total_round > 0:
                est_jct = (
                    runtime + max(total_round - round_executed, 0) * avg_round_time
                )
            else:
                est_jct = 2 * runtime
            return est_jct

        except Exception as e:
            self.logger.print(e, Msg_level.WARNING)
            return 1000 * std_round_time


class SC_client_db_portal(Client_db):
    def __init__(self, gconfig: dict, logger: Propius_logger):
        """Initialize client db portal

        Args:
            gconfig: config dictionary
                public_max: upper bound of the score
                client_manager: list of client manager address
                    ip:
                    client_db_port
                client_expire_time: expiration time of clients in the db
                job_public_constraint: name of public constraint
            logger
        """

        # TODO determine which client db to connect, by default db 0
        super().__init__(gconfig, 0, False, logger)
        self.public_max = gconfig["public_max"]

    def get_client_size(self) -> int:
        """Get client dataset size"""
        num = 0
        try:
            info = self.r.ft("client").info()
            num = int(info["num_docs"])
        except Exception as e:
            self.logger.print(e, Msg_level.ERROR)

        return num

    def get_client_proportion(self, public_constraint: tuple) -> float:
        """Get client subset size

        Args:
            public_constraint: lower bounds of the client specification.
                                Every client in the returned subset has
                                spec greater or equal to this constraint
        """

        client_size = self.get_client_size()
        if client_size == 0:
            return 0.01

        qstr = ""
        for idx, name in enumerate(self.public_constraint_name):
            qstr += f"@{name}: [{public_constraint[idx]}, {self.public_max[name]}] "

        size = 0
        try:
            q = Query(qstr).no_content().paging(0, 10000)
            size = int(self.r.ft("client").search(q).total)
        except Exception as e:
            self.logger.print(e, Msg_level.ERROR)

        if size == 0:
            return 0.01

        return size / client_size

    def get_client_subset_size(self, query: str) -> int:
        """Get client subset size using input query

        Args:
            query: query which defines a client subset
        """
        q = Query(query).no_content().paging(0, 10000)
        try:
            size = int(self.r.ft("client").search(q).total)
        except Exception as e:
            self.logger.print(e, Msg_level.ERROR)

        return size
