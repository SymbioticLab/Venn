from propius.controller.util import get_time, Propius_logger, Monitor
from propius.controller.config import PROPIUS_ROOT, PROPIUS_CONTROLLER_ROOT
import matplotlib.pyplot as plt
import asyncio
import os


class SC_monitor(Monitor):
    def __init__(self, logger: Propius_logger, path: str, plot: bool = False):
        super().__init__("Scheduler", logger, plot)
        # self.job_size_latency_map = {}
        # self.job_request_map = {}
        self.plot = plot
        self.plot_path = path

    async def request(self, job_id: int):
        self._request()
        # self.job_request_map[job_id] = time.time()

    # async def request_end(self, job_id: int, job_size: int):
    #     async with self.lock:
    #         runtime = time.time() - self.job_request_map[job_id]

    #         if job_size not in self.job_size_latency_map:
    #             self.job_size_latency_map[job_size] = 0
    #         self.job_size_latency_map[job_size] += runtime

    #         del self.job_request_map[job_id]

    # def _plot_time(self):
    #     lists = sorted(self.job_size_latency_map.items())
    #     x, y = zip(*lists)
    #     plt.scatter(x, y)
    #     plt.title('Scheduling Alg latency')
    #     plt.xlabel('Number of jobs')
    #     plt.ylabel('Latency (sec)')

    def report(self):
        # for size, latency_list in self.job_size_latency_map.items():
        #     self.job_size_latency_map[size] = sum(
        #         latency_list) / len(latency_list)

        # lists = sorted(self.job_size_latency_map.items())
        # if len(lists) > 0:
        #     x, y = zip(*lists)
        #     str1 = self._gen_report()
        #     with open(f'./propius/log/SC-{self.sched_alg}-{get_time()}.txt', 'w') as file:
        #         file.write(str1)
        #         file.write("\n")
        #         for idx, job_size in enumerate(x):
        #             file.write(f"Job size: {job_size}, latency: {y[idx]}\n")

        self._gen_report()
        if self.plot:
            fig = plt.gcf()
            # plt.subplot(2, 1, 1)
            # self._plot_time()
            # plt.subplot(2, 1, 2)
            self._plot_request()
            # plt.tight_layout()
            plot_file = PROPIUS_ROOT / self.plot_path / "sc.jpg"
            os.makedirs(os.path.dirname(plot_file), exist_ok=True)
            fig.savefig(plot_file)
