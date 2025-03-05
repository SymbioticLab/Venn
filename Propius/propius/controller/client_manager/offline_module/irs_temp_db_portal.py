from propius.controller.client_manager.offline_module.base_temp_db_portal import (
    CM_temp_client_db_portal,
)
from redis.commands.json.path import Path
from redis.commands.search.query import Query
from propius.controller.client_manager.cm_db_portal import CM_job_db_portal
from propius.controller.util import Msg_level, Propius_logger, geq, Job_group
import json
import time
import random


class IRS_temp_client_db_portal(CM_temp_client_db_portal):
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
        super().__init__(gconfig, cm_id, cm_job_db, logger, flush)

        self.tier_num = gconfig["tier_num"]

    def client_assign(self):
        """Assigning available job in job group to all clients in temporary datastore"""

        for key, job_list in self.job_group.key_job_group_map.items():
            try:
                condition_q = self.job_group[key].str()
                q = Query(condition_q).paging(0, 1000)
                result = self.r.ft("temp").search(q)

                job_list_str = str(job_list)

                self.logger.print(f"binding job group: {job_list}", Msg_level.INFO)

                if self.tier_num > 1 and len(job_list) > 0 and len(result.docs) > 0:
                    front_job_id = job_list[0]
                    tier_lower_bound = [0 for _ in range(self.tier_num + 1)]
                    option_list = []
                    rem_job_list_str = str(job_list[1:])
                    for doc in result.docs:
                        try:
                            temp_client = json.loads(doc.json)
                            option_list.append(temp_client["temp"]["option"])
                        except:
                            pass

                    option_list.sort()
                    tier_len = int(len(option_list) / self.tier_num)
                    for i in range(self.tier_num):
                        tier_lower_bound[i] = option_list[i * tier_len]
                    tier_lower_bound[-1] = option_list[-1]

                    sched, resp = -1, -1
                    try:
                        sched = self.job_db_portal.get_field(
                            front_job_id, "total_sched"
                        )
                        timestamp = self.job_db_portal.get_field(
                            front_job_id, "timestamp"
                        )
                        resp = time.time() - timestamp - sched
                    except Exception:
                        pass
                    c = resp / sched if sched > 0 else 1

                    u = random.randint(0, self.tier_num - 1)
                    gu = (
                        tier_lower_bound[0] / tier_lower_bound[u]
                        if tier_lower_bound[u] > 0
                        else 1
                    )

                    if self.tier_num + gu * c < c + 1:
                        self.logger.print(
                            f"job {front_job_id} tier-matching, tier_num: {self.tier_num}"
                            f" u: {u}, gu: {gu}, c: {c}",
                            Msg_level.INFO,
                        )
                        for doc in result.docs:
                            try:
                                temp_client = json.loads(doc.json)
                                client_id = doc.id
                                option = temp_client["temp"]["option"]
                                if (
                                    option >= tier_lower_bound[u]
                                    and option < tier_lower_bound[u + 1]
                                ):
                                    self.r.execute_command(
                                        "JSON.SET", client_id, "$.temp.job_ids", job_list_str
                                    )
                                    self.logger.print(
                                        f"bind client with job: {client_id} {job_list_str}",
                                        Msg_level.INFO,
                                    )
                                else:
                                    self.r.execute_command(
                                        "JSON.SET", client_id, "$.temp.job_ids", rem_job_list_str
                                    )
                                    self.logger.print(
                                        f"bind client with job: {client_id} {rem_job_list_str}",
                                        Msg_level.INFO,
                                    )
                            except:
                                pass

                    else:
                        self.logger.print(
                            f"job {front_job_id} not tier-matching,"
                            f"tier_num: {self.tier_num}"
                            f" u: {u}, gu: {gu}, c: {c}",
                            Msg_level.INFO,
                        )
                        
                        # self.logger.print(
                        #     f"binding {len(result.docs)} clients with job: {job_list_str} ",
                        #     Msg_level.INFO,
                        # )
                        for doc in result.docs:
                            client_id = doc.id
                            try:
                                self.r.execute_command(
                                    "JSON.SET", client_id, "$.temp.job_ids", job_list_str
                                )
                                self.logger.print(
                                    f"bind client with job: {client_id} {job_list_str}",
                                    Msg_level.INFO,
                                )
                            except:
                                # self.logger.print(f"temp client {client_id} not found", Msg_level.WARNING)
                                continue

                elif self.tier_num <= 1:
                    # self.logger.print(
                    #     f"binding {len(result.docs)} clients with job: {job_list_str} ",
                    #     Msg_level.INFO,
                    # )
                    for doc in result.docs:
                        client_id = doc.id
                        try:
                            self.r.execute_command(
                                "JSON.SET", client_id, "$.temp.job_ids", job_list_str
                            )
                            self.logger.print(
                                f"bind client with job: {client_id} {job_list_str}",
                                Msg_level.INFO,
                            )
                        except:
                            # self.logger.print(f"temp client {client_id} not found", Msg_level.WARNING)
                            continue

            except Exception as e:
                self.logger.print(e, Msg_level.ERROR)
