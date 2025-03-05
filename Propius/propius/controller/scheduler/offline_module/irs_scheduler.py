"""IRS scheduler"""

from propius.controller.util import Propius_logger, Msg_level
from propius.controller.scheduler.offline_module.base_scheduler import Scheduler
from propius.controller.channels import propius_pb2


class IRS_scheduler(Scheduler):
    def __init__(self, gconfig: dict, logger: Propius_logger):
        super().__init__(gconfig, logger)

    async def job_regist(self, job_id: int):
        # Get constraints
        constraints = self.job_db_portal.get_job_constraints(job_id)
        if not constraints:
            return False
        # Insert cst to job group
        self.job_group.insert_key(constraints)
        self.logger.print(f"insert new constraint group: {constraints}", Msg_level.INFO)

    async def job_request(self, job_id: int):
        pass

    async def offline(self) -> bool:
        try:
            constraints_client_map = {}
            constraints_alloc_map = {}
            origin_group_condition = {}
            job_time_ratio_map = {}
            # Clear past job group info
            self.job_group.clear_group_info()

            for cst in self.job_group.key_list:
                # iterate over constraint, get updated and sorted job list
                if not self.job_db_portal.get_job_list(
                    cst, self.job_group.key_job_group_map[cst]
                ):
                    self.job_group.remove_key(cst)

                for job_id in self.job_group.key_job_group_map[cst]:
                    sched, resp = self.job_db_portal.get_sched_resp(job_id)
                    job_time_ratio_map[job_id] = resp / sched if sched > 0 else 1

            self.logger.print(f"finding eligible client size", Msg_level.INFO)
            # search elig client size for each group
            for cst in self.job_group.key_list:
                constraints_client_map[
                    cst
                ] = self.client_db_portal.get_client_proportion(cst)

            # Update group query 1
            client_size = self.client_db_portal.get_client_size()
            self.job_group.key_list.sort(key=lambda x: constraints_client_map[x])
            bq = ""
            for cst in self.job_group.key_list:
                this_q = ""
                for idx, name in enumerate(self.public_constraint_name):
                    this_q += f"@{name}: [{cst[idx]}, {self.public_max[name]}] "

                origin_group_condition[cst] = this_q

                q = this_q + bq
                self.job_group[cst].insert_condition_and(q)
                client_subset_size = self.client_db_portal.get_client_subset_size(q)
                constraints_alloc_map[cst] = (
                    client_subset_size / client_size if client_size != 0 else 0.01
                )
                bq = bq + f" -({this_q})"

            # Update group query 2
            self.job_group.key_list.sort(
                key=lambda x: constraints_client_map[x], reverse=True
            )
            for idx, cst in enumerate(self.job_group.key_list):
                for h_cst in self.job_group.key_list[idx + 1 :]:
                    m = self.job_db_portal.get_affected_len(
                        self.job_group.key_job_group_map[cst],
                        self.job_group.key_job_group_map[h_cst],
                        constraints_client_map[cst],
                        constraints_client_map[h_cst],
                    )
                    m_h = len(self.job_group.key_job_group_map[h_cst])
                    if (
                        m / constraints_alloc_map[cst]
                        > m_h / constraints_alloc_map[h_cst]
                    ):
                        or_condition = (
                            origin_group_condition[cst] + origin_group_condition[h_cst]
                        )
                        self.job_group[cst].insert_condition_or(or_condition)
                        self.job_group[h_cst].insert_condition_and(
                            f"-({self.job_group[cst].str()})"
                        )
                    else:
                        break
                self.logger.print(
                    f"{cst} group, condition: {self.job_group[cst].str()}",
                    Msg_level.INFO,
                )
            return True
        except Exception as e:
            self.logger.print(e, Msg_level.ERROR)
            return False
