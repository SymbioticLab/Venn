from propius.controller.client import Propius_client
from propius.parameter_server.client import Propius_ps_client
import time


class Client:
    def __init__(self, config: dict, verbose: bool = False, logging: bool = False):
        """Init client library.

        Args:
            config:
                public_specifications: dict
                private_specifications: dict
                load_balancer_ip: load balancer IP
                load_balancer_port: load balancer port
                option: float
                leaf_ps_ip: parameter server IP
                leaf_ps_port: parameter server port
                max_message_length: maximum upload and download size
            verbose: whether to print or not
            logging: whether to log or not

        Raises:
            ValueError: missing config args
        """

        self.client_controller = Propius_client(config, verbose, logging)

        self.client_ps = None
        self.id = -1
        self.config = config
        self.verbose = verbose
        self.logging = logging

        self.task_id = -1
        self.round = -1

    def get(self, timeout: float = 60):
        """Get task parameters and config.

        This is a blocking call, and could be called multiple times

        Args:
            timeout: default to 60 seconds
        Returns:
            (task_meta, task_data) if success
            None if fail
        Raises:
            RuntimeError: if can't establish connection after multiple trial
        """
        start_time = time.time()

        self.task_id, self.round = -1, -1

        self.client_controller.connect()
        while True:
            task_ids, task_private_constraint = [], []
            task_ids, task_private_constraint = self.client_controller.client_check_in()
            self.id = self.client_controller.id
            self.client_ps = Propius_ps_client(
                self.config, self.id, self.verbose, self.logging
            )

            ttl = 5
            while not task_ids:
                if time.time() - start_time > timeout or ttl <= 0:
                    return None
                time.sleep(2)
                ttl -= 1
                task_ids, task_private_constraint = self.client_controller.client_ping()

            if task_ids:
                task_id = self.client_controller.select_task(
                    task_ids, task_private_constraint
                )

                if task_id >= 0:
                    result = self.client_controller.client_accept(task_id)
                    if result:
                        round = result[2]
                        code, meta, data = self.client_ps.get(task_id, round)

                        if code == 1:
                            self.task_id = task_id
                            self.round = round
                            return (meta, data)

            if time.time() - start_time > timeout:
                break
            time.sleep(2)
        return None

    def push(self, data: list) -> bool:
        """Push local execution result to parameter server.
        This call should be called after a get call, and should be
        only called once before the next get call.

        Args:
            data: list of tensor
        Returns:
            a boolean indicating whether the upload succeeded
        Raises:
            RuntimeError: if can't establish connection after multiple trial
        """
        if self.task_id == -1 or self.round == -1:
            return False

        code = self.client_ps.push(self.task_id, self.round, data)
        self.task_id, self.round = -1, -1
        self.client_controller.close()
        return code == 1
