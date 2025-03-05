from propius.controller.job.propius_job import Propius_job
from propius.parameter_server.job.propius_ps import Propius_ps_job
import time


class Job:
    def __init__(self, config: dict, verbose: bool = False, logging: bool = False):
        """Init Propius_job class

        Args:
            job_config:
                public_constraint: dict, a tuple of scalars
                private_constraint: dict, specifying desired dataset and its size
                total_round: optional
                demand: estimated demand per round
                job_manager_ip: job manager IP
                job_manager_port: job manager port
                ip: ip of the job server
                port: port number of the job server
                root_ps_ip: root parameter server IP
                root_ps_port: root parameter server port
                max_message_length: maximum upload and download size
            verbose: whether to print or not
            logging: whether to log or not

        Raises:
            ValueError: missing config args
        """

        self.job_controller = Propius_job(config, verbose, logging)

        self.id = -1
        self.job_ps = None
        self.config = config
        self.verbose = verbose
        self.logging = logging

        self.total_round = config["total_round"] if "total_round" in config else -1
        self.demand = config["demand"]

        self.round = 0

    def register(self) -> bool:
        """Register job. Send job config to Propius job manager.

        Returns:
            a boolean indicating the status of registration

        Raise:
            RuntimeError: if can't send register request after multiple trial
        """
        if self.job_controller.register():
            self.id = self.job_controller.id

            self.job_ps = Propius_ps_job(
                self.config, self.id, self.verbose, self.logging
            )
            return True
        else:
            return False

    def request(self, meta: dict, data: list, demand: int = -1) -> bool:
        """Send round request to Propius.
        If the controller accepts the request, round metadata and parameter data are sent to the paremeter server for client retrieval.

        Args:
            meta: a dictionary of configuration
            data: a list of tensor
            demand: optional. The round demand for this round will change if specified

        Returns:
            a boolean indicating whether the call was successful.
            If return False, it might be due to the request time exceeds the
            total round configuration during initalization.

        Raise:
            RuntimeError: if can't send request after multiple trial
        """

        new_demand = demand > 0
        this_round_demand = self.demand if not new_demand else demand

        this_round = self.job_controller.start_request(new_demand, this_round_demand)
        self.round = this_round
        if this_round != -1:
            if self.job_ps.put(this_round, this_round_demand, meta, data) == 1:
                return True
        return False

    def reduce(self, timeout: float = 60):
        """Get round result from parameter server, as well as terminate round request at controller.

        This is a blocking call. It can be called multiple times if the previous calls are not successful. Another request call is needed after a successful reduce call.

        Args:
            timeout: default to 60 seconds

        Returns:
            (metadata, data) if successful (round demand satisfied), else None

        Raises:
            RuntimeError: if can't send end request after multiple trial or internal parameter server error
        """
        if self.round == -1:
            return None

        start_time = time.time()
        while True:
            code, meta, data = self.job_ps.get(self.round)
            if code == 1:
                self.job_controller.end_request()
                self.round = -1
                return (meta, data)

            elif code == 3:
                raise RuntimeError("error from parameter server")

            if time.time() - start_time >= timeout:
                break
            time.sleep(5)

        return None

    def complete(self):
        """Job completion call. Job metadata and parameter entry will be deleted after this call.

        Raise:
            RuntimeError: if can't send request after multiple trial
        """
        self.job_controller.complete_job()
        self.job_ps.delete()
