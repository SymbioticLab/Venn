import redis
from redis.commands.json.path import Path
from redis.commands.search.query import Query
import time
import json
from propius.controller.database import Job_db
from propius.controller.util import Msg_level, Propius_logger

class JM_job_db_portal(Job_db):
    def __init__(self, gconfig: dict, logger: Propius_logger):
        """Init job database portal class

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

        super().__init__(gconfig, True, logger)

    def register(
            self,
            job_id: int,
            public_constraint: tuple,
            private_constraint: tuple,
            job_ip: str,
            job_port: int,
            total_demand: int,
            total_round: int) -> bool:
        """Register incoming job to the database

        Return False if the job ID is already in the database. 
        Set expiration time of the job

        Args:
            job_id
            public_constraint: a tuple of values of constraints
            private_constraint: a tuple of values of constraints, first is the dataset name
            job_ip
            job_port
            total_demand
            total_round
        """

        if len(public_constraint) != len(self.public_constraint_name):
            raise ValueError("Public constraint len does not match required")
        if len(private_constraint) != len(self.private_constraint_name):
            raise ValueError("Private constraint len does not match required")

        job_dict = {
            "timestamp": time.time(),
            "total_sched": 0,
            "start_sched": 0,
            "ip": job_ip,
            "port": job_port,
            "total_demand": total_demand,
            "total_round": total_round,
            "attained_service": 0,
            "round": -1,
            "demand": 0,
            "amount": 0,
            "score": 0,
        }
        constraint_dict = {"public_constraint":
                           {
                               self.public_constraint_name[i]: public_constraint[i]
                               for i in range(len(public_constraint))
                           },
                           "private_constraint":
                           {
                               self.private_constraint_name[i]: private_constraint[i]
                               for i in range(len(private_constraint))
                           },
                           }
        job_dict.update(constraint_dict)
        job = {
            "job": job_dict,
        }

        with self.r.json().pipeline() as pipe:
            while True:
                try:
                    id = f"job:{job_id}"
                    pipe.watch(id)
                    if pipe.get(id):
                        pipe.unwatch()
                        return False
                    pipe.set(id, Path.root_path(), job)
                    pipe.expire(f"job:{id}", self.job_exp_time)
                    pipe.unwatch()
                    return True
                except redis.WatchError:
                    pass
                except Exception as e:
                    self.logger.print(e, Msg_level.ERROR)
                    return False
                
    def prune(self):
        """Prune job database.
        
        If a job doesn't send request to Propius for more than max_silent_time, 
        the job will be removed
        """
        result = None
        try:
            q = Query('*').paging(0, 100)
            result = self.r.ft('job').search(q)
        except Exception as e:
            self.logger.print(e, Msg_level.WARNING)

        if result:
            for doc in result.docs:
                job = json.loads(doc.json)
                job_id = int(doc.id.split(':')[1])
                if job['job']['start_sched'] > 0 and \
                    time.time() - job['job']['start_sched'] >= self.gconfig['job_max_silent_time']:

                    self.remove_job(job_id)

    def request(self, job_id: int, demand: int) -> tuple:
        """Update job metadata based on request

        Return False if the job_id is not in the database. 
        Increment job round, update job demand for new round, 
        and clear job allocation amount counter. Start sched_time counter

        Args:
            job_id
            demand

        Returns:
            ack: boolean for request status
            round: current round
        """
        job_finished = False

        with self.r.json().pipeline() as pipe:
            while True:
                try:
                    id = f"job:{job_id}"
                    pipe.watch(id)
                    if not pipe.get(id):
                        pipe.unwatch()
                        break
                    cur_round = int(self.r.json().get(id, "$.job.round")[0]) + 1
                    total_round = int(
                        self.r.json().get(
                            id, "$.job.total_round")[0])
                    if not self.gconfig["allow_exceed_total_round"]:
                        if (total_round > 0 and cur_round >= total_round) or \
                            (total_round == 0 and cur_round >= self.gconfig["max_round"]):
                            job_finished = True
                            break

                    pipe.multi()
                    pipe.execute_command(
                        'JSON.NUMINCRBY', id, "$.job.round", 1)
                    pipe.execute_command(
                        'JSON.SET', id, "$.job.demand", demand)
                    pipe.execute_command('JSON.SET', id, "$.job.amount", 0)
                    pipe.execute_command(
                        'JSON.SET', id, "$.job.start_sched", time.time())
                    pipe.execute()
                    return (True, cur_round)
                except redis.WatchError:
                    pass
                except Exception as e:
                    self.logger.print(e, Msg_level.ERROR)

        if job_finished:
            self.logger.print(f"job {job_id} reached final round", Msg_level.ERROR)
            self.remove_job(job_id)
        return (False, -1)
    
    def update_total_demand_estimate(self, job_id: int, demand: int):
        """Update total demand estimate.
        
        If total round is known, update total demand by multiplying total round with current demand.
        If total round is unknown, update total demand by doubling the attained service number,

        Args:
            job_id
            demand
        """

        with self.r.json().pipeline() as pipe:
            while True:
                try:
                    id = f"job:{job_id}"
                    pipe.watch(id)
                    if not pipe.get(id):
                        pipe.unwatch()
                        break
                    
                    total_round = int(
                        self.r.json().get(id, "$.job.total_round")[0]
                    )
                    attained_service = int(
                        self.r.json().get(id, "$.job.attained_service")[0]
                    )
                    
                    if total_round > 0:
                        round = int(
                            self.r.json().get(id, "$.job.round")[0]
                        )
                        total_demand = attained_service + max(total_round - round, 0) * demand
                    else:
                        total_demand = max(2 * attained_service, demand)
                    
                    pipe.multi()
                    pipe.execute_command(
                        'JSON.SET', id, "$.job.total_demand", total_demand)
                    pipe.execute()
                    break
                except redis.WatchError:
                    pass
                except Exception as e:
                    self.logger.print(e, Msg_level.ERROR)

    def end_request(self, job_id: int) -> bool:
        """Update job metadata based on end request
        
        Set job allocation amount as job demand to indicate allocation has finished. 
        Update total scheduling time.

        Args:
            job_id
        """

        with self.r.json().pipeline() as pipe:
            while True:
                try:
                    id = f"job:{job_id}"
                    pipe.watch(id)
                    if not pipe.get(id):
                        pipe.unwatch(id)
                        return False
                    demand = int(self.r.json().get(id, "$.job.demand")[0])
                    amount = int(self.r.json().get(id, "$.job.amount")[0])
                    if amount >= demand:
                        pipe.unwatch()
                        return True
                    start_sched = float(
                        self.r.json().get(
                            id, "$.job.start_sched")[0])
                    pipe.multi()
                    pipe.execute_command(
                        'JSON.SET', id, "$.job.amount", demand)
                    sched_time = time.time() - start_sched
                    pipe.execute_command(
                        'JSON.NUMINCRBY', id, "$.job.total_sched", sched_time)
                    pipe.execute_command(
                        'JSON.NUMINCRBY', id, "$.job.attained_service", demand
                    )
                    pipe.execute()
                    return True
                except redis.WatchError:
                    pass
                except Exception as e:
                    self.logger.print(e, Msg_level.ERROR)
                    return False

    def finish(self, job_id: int) -> tuple[tuple, int, int, float, float]:
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

        return self.remove_job(job_id)