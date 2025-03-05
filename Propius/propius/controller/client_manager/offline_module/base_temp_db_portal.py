import redis
from redis.commands.json.path import Path
from redis.commands.search.query import Query
from propius.controller.database import Temp_client_db
from propius.controller.client_manager.cm_db_portal import CM_job_db_portal
from propius.controller.util import Msg_level, Propius_logger, geq, Job_group
import ast
import json
import random


class CM_temp_client_db_portal(Temp_client_db):
    def __init__(
        self,
        gconfig,
        cm_id: int,
        cm_job_db: CM_job_db_portal,
        logger: Propius_logger,
        flush: bool = False,
    ):
        """Initialize temp client db portal

        Args:
            gconfig: config dictionary
                client_manager: list of client manager address
                    ip:
                    client_db_port
                client_expire_time: expiration time of clients in the db
                job_public_constraint: name of public constraint
                flush: whether to flush the db first

            cm_id: id of the client manager is the user is client manager
            cm_job_db: job db portal
            is_cm: bool indicating whether the user is client manager
            logger
        """

        super().__init__(gconfig, cm_id, True, logger, flush)
        self.job_group = Job_group()
        self.tier_num = gconfig["tier_num"] if "tier_num" in gconfig else 0
        self.job_db_portal = cm_job_db
        self.max_task_offer_list_len = gconfig["max_task_offer_list_len"]

    def update_job_group(self, new_job_group: Job_group):
        self.job_group = new_job_group

    def client_assign(self):
        """Assigning available job in job group to all clients in temporary datastore"""
        for key, job_list in self.job_group.key_job_group_map.items():
            try:
                condition_q = self.job_group[key].str()
                q = Query(condition_q).paging(0, 1000)
                result = self.r.ft("temp").search(q)

                self.logger.print(f"binding job group: {job_list}", Msg_level.INFO)

                job_list = filter(lambda x: self.job_db_portal.is_available(x), job_list)

                for doc in result.docs:
                    try:
                        client_id = doc.id
                        # get client attributes
                        temp_client = json.loads(doc.json)
                        client_attr_list = []
                        for name in self.public_constraint_name:
                            client_attr_list.append(float(temp_client["temp"][name]))
                        client_attr_tuple = tuple(client_attr_list)

                        assigned_job_list = []
                        for job_id in job_list:
                            if len(assigned_job_list) < self.max_task_offer_list_len:
                                if geq(
                                    client_attr_tuple,
                                    self.job_db_portal.get_job_constraints(job_id),
                                ):
                                    assigned_job_list.append(job_id)
                            else:
                                break
                        assigned_job_str = str(assigned_job_list)

                        self.logger.print(
                            f"bind client with job: {client_id} {assigned_job_str} ",
                            Msg_level.INFO,
                        )
                        self.r.execute_command(
                            "JSON.SET", client_id, "$.temp.job_ids", assigned_job_str
                        )
                    except:
                        pass

            except Exception as e:
                self.logger.print(e, Msg_level.ERROR)

    def insert(self, id: int, specifications: tuple, option: float = 0):
        """Insert client metadata to database, set expiration time and start time

        Args:
            id
            specification: a tuple of public spec values
            option: a optional value
        """

        if len(specifications) != len(self.public_constraint_name):
            self.logger.print(
                "specification length does not match required", Msg_level.ERROR
            )
        client_dict = {"job_ids": "[]", "option": option}
        spec_dict = {
            self.public_constraint_name[i]: specifications[i]
            for i in range(len(specifications))
        }
        client_dict.update(spec_dict)
        client = {"temp": client_dict}
        try:
            self.r.json().set(f"temp:{id}", Path.root_path(), client)
            self.r.expire(f"temp:{id}", self.client_exp_time)
        except Exception as e:
            self.logger.print(e, Msg_level.ERROR)

    def get_task_id(self, client_id: int, specifications: tuple) -> list:
        """Return task id of client id.

        Args:
            client_id

        Returns:
            a list of task id
        """
        task_list = []
        try:
            id = f"temp:{client_id}"
            if self.r.execute_command("EXISTS", id):
                result = str(self.r.json().get(id, "$.temp.job_ids")[0])
                task_list = ast.literal_eval(result)

        except Exception as e:
            self.logger.print(e, Msg_level.ERROR)

        return task_list

    def remove_client(self, client_id: int):
        """Remove the temp client from database.

        Args:
            client_id
        """

        with self.r.json().pipeline() as pipe:
            while True:
                try:
                    id = f"temp:{client_id}"
                    pipe.watch(id)
                    pipe.delete(id)
                    pipe.unwatch()
                    self.logger.print(
                        f"remove temp client:{client_id}", Msg_level.WARNING
                    )
                    return
                except redis.WatchError:
                    pass
                except Exception as e:
                    return
