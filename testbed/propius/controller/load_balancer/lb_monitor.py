from propius.controller.util import get_time, Propius_logger, Monitor
from propius.controller.config import PROPIUS_ROOT, PROPIUS_CONTROLLER_ROOT
import matplotlib.pyplot as plt
import asyncio
import os


class LB_monitor(Monitor):
    def __init__(self, logger: Propius_logger, path: str, plot: bool = False):
        super().__init__("Load balancer", logger, plot)
        self.plot = plot
        self.plot_path = path

    def request(self):
        self._request()

    def report(self):
        self._gen_report()
        if self.plot:
            fig = plt.gcf()
            self._plot_request()
            plot_file = PROPIUS_ROOT / self.plot_path / "lb.jpg"
            os.makedirs(os.path.dirname(plot_file), exist_ok=True)
            fig.savefig(plot_file)
