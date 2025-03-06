import asyncio
import time
import matplotlib.pyplot as plt
from propius.controller.util import Msg_level, Propius_logger, get_time, Monitor
from propius.controller.config import PROPIUS_ROOT, PROPIUS_CONTROLLER_ROOT
import os


class JM_monitor(Monitor):
    def __init__(self, logger: Propius_logger, path: str, plot: bool = False):
        super().__init__("Job manager", logger, plot)
        self.plot_path = path

        self.total_job = 0

        self.start_time = int(time.time())
        self.job_time_num = [0]
        self.job_timestamp = [0]

        self.constraint_jct_dict = {}
        self.constraint_sched_dict = {}
        self.constraint_cnt = {}
        self.plot = plot

    async def job_register(self):
        self.total_job += 1
        if self.plot:
            runtime = int(time.time()) - self.start_time
            self.job_timestamp.append(runtime)
            self.job_timestamp.append(self.job_timestamp[-1])
            self.job_time_num.append(self.job_time_num[-1])
            self.job_time_num.append(self.job_time_num[-1] + 1)

    async def job_finish(
        self,
        constraint: tuple,
        demand: int,
        total_round: int,
        job_runtime: float,
        sched_latency: float,
    ):
        runtime = int(time.time()) - self.start_time
        self.job_timestamp.append(runtime)
        self.job_timestamp.append(self.job_timestamp[-1])
        self.job_time_num.append(self.job_time_num[-1])
        self.job_time_num.append(self.job_time_num[-1] - 1)

        key = (constraint, demand, total_round)
        if key not in self.constraint_jct_dict:
            self.constraint_jct_dict[key] = 0
            self.constraint_sched_dict[key] = 0
            self.constraint_cnt[key] = 0
        self.constraint_jct_dict[key] += job_runtime
        self.constraint_cnt[key] += 1
        self.constraint_sched_dict[key] += sched_latency

    async def request(self):
        self._request()

    def _plot_job(self):
        plt.plot(self.job_timestamp, self.job_time_num)
        plt.title("Job trace")
        plt.ylabel("Number of jobs")
        plt.xlabel("Time (sec)")

    def report(self):
        self._gen_report()
        self.logger.print(f"total job: {self.total_job}", Msg_level.INFO)

        for constraint, sum_jct in self.constraint_jct_dict.items():
            cnt = self.constraint_cnt[constraint]
            avg_jct = sum_jct / cnt
            sum_sched = self.constraint_sched_dict[constraint]
            avg_sched = sum_sched / cnt

            self.logger.print(
                f"job group: {constraint}, num: {cnt}, avg JCT: {avg_jct:.3f}, avg sched latency: {avg_sched:.3f}\n"
            )

        if self.plot:
            fig = plt.gcf()
            
            plt.subplot(2, 1, 1)
            self._plot_job()
            plt.subplot(2, 1, 2)
            self._plot_request()
            plt.tight_layout()

            plot_file = PROPIUS_ROOT / self.plot_path / "jm.jpg"
            os.makedirs(os.path.dirname(plot_file), exist_ok=True)
            fig.savefig(plot_file)
