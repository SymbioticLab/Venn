from propius.parameter_server.channels import (
    parameter_server_pb2,
    parameter_server_pb2_grpc,
)
from propius.parameter_server.util.commons import Msg_level, get_time
import pickle
import grpc
import time
import logging


class Propius_ps_job:
    def __init__(self, config, id=0, verbose: bool = False, logging: bool = False):
        """Init Propius_ps_job class

        Args:
            config:
                root_ps_ip
                root_ps_port
                max_message_length
            id: job_id received from job_manager
            verbose: whether to print or not
            logging: whether to log or not
        Raises:
            ValueError: missing config args
        """
        try:
            self.id = id
            self._ps_ip = config["root_ps_ip"]
            self._ps_port = config["root_ps_port"]
            self._ps_channel = None
            self._ps_stub = None
            self.max_message_length = config["max_message_length"]

            self.verbose = verbose
            self.logging = logging
        except Exception:
            raise ValueError("Missing config arguments")

    def _cleanup_routine(self):
        try:
            self._ps_channel.close()
        except Exception:
            pass

    def _custom_print(self, message: str, level: int = Msg_level.PRINT):
        if self.verbose:
            print(f"{get_time()} {message}")
        if self.logging:
            if level == Msg_level.DEBUG:
                logging.debug(message)
            elif level == Msg_level.INFO:
                logging.info(message)
            elif level == Msg_level.WARNING:
                logging.warning(message)
            elif level == Msg_level.ERROR:
                logging.error(message)

    def __del__(self):
        self._cleanup_routine()

    def _connect_ps(self) -> None:
        channel_options = [
            ("grpc.max_receive_message_length", self.max_message_length),
            ("grpc.max_send_message_length", self.max_message_length),
        ]
        self._ps_channel = grpc.insecure_channel(
            f"{self._ps_ip}:{self._ps_port}", options=channel_options
        )
        self._ps_stub = parameter_server_pb2_grpc.Parameter_serverStub(self._ps_channel)

        self._custom_print(
            f"Job {self.id}: connecting to parameter_server at {self._ps_ip}:{self._ps_port}",
            Msg_level.INFO,
        )

    def connect(self, num_trial: int = 1):
        """Connect to Propius parameter server

        Raise:
            RuntimeError: if can't establish connection after multiple trial
        """
        for _ in range(num_trial):
            try:
                self._connect_ps()
                return
            except Exception as e:
                self._custom_print(e, Msg_level.ERROR)
                time.sleep(5)

        raise RuntimeError("Unable to connect to Propius PS at the moment")

    def close(self):
        """Clean up allocation, close connection to Propius parameter server."""
        self._cleanup_routine()

    def put(self, round: int, demand: int, meta: dict, data: list):
        """Upload data and metadata to Propius PS for new a new round.
        This RPC will clear previous job entries in both parameter store and
        aggregation store, and set new ones for dispatch and aggregation. The demand should be
        consistent with the scheduled demand. The dispatch entry in parameter store might
        timeout if client resource is scarce.
        Both job entry in parameter store and aggregation store will have a new ttl.

        Args:
            round: current round number
            demand: minimum number of allocation for a round to be successful
            meta: a dict for metadata
            data: a list of parameters (for example, one entry can be one layer)

        Returns:
            code: status code, 1 is successful

        Raises:
            RuntimeError: if can't send register request after multiple trial
        """

        meta["demand"] = demand
        put_msg = parameter_server_pb2.job(
            code=5,
            job_id=self.id,
            round=round,
            meta=pickle.dumps(meta),
            data=pickle.dumps(data),
        )

        for _ in range(3):
            self.connect()
            try:
                self._custom_print(
                    f"Job {self.id}: send PUT request for round: {round}, demand: {demand}"
                )
                return_msg = self._ps_stub.JOB_PUT(put_msg)
                self._cleanup_routine()
                return return_msg.code
            except Exception as e:
                self._custom_print(e, Msg_level.ERROR)
                self._cleanup_routine()
                time.sleep(5)

        raise RuntimeError("Unable to send put request to Propius PS at the moment")

    def get(self, round: int):
        """Ask for round result. The call will be successful if the round is the active round,
        and all the demanded client updates are received at the parameter server. If the result
        status is pending, another get call is required. If the calling interval is too long,
        the entry in parameter server may time out. Check the server configuration for more info.

        Args:
            round: current round

        Returns:
            code: status code, 1-successful, 6: waiting for complete result, 3: error
            meta: metadata
            data: parameter data
        Raises
            RuntimeError: if can't send request after multiple trial
        """

        get_msg = parameter_server_pb2.job(
            code=0,
            job_id=self.id,
            round=round,
            meta=pickle.dumps(""),
            data=pickle.dumps(""),
        )
        for _ in range(3):
            self.connect()
            try:
                self._custom_print(
                    f"Job {self.id}: send GET request for round: {round}"
                )
                result = self._ps_stub.JOB_GET(get_msg)
                self._cleanup_routine()
                return (
                    result.code,
                    pickle.loads(result.meta),
                    pickle.loads(result.data),
                )
            except Exception as e:
                self._custom_print(e, Msg_level.ERROR)
                self._cleanup_routine()
                time.sleep(5)

        raise RuntimeError("Unable to send job get request to Propius PS at the moment")

    def delete(self):
        """Delete job entry at Propius parameter server. Call this when all rounds are finished.

        Raise:
            RuntimeError: if can't send complete_job request after multiple trial
        """
        delete_msg = parameter_server_pb2.job(
            code=0,
            job_id=self.id,
            round=-1,
            meta=pickle.dumps(""),
            data=pickle.dumps(""),
        )

        for _ in range(3):
            self.connect()
            try:
                self._ps_stub.JOB_DELETE(delete_msg)
                self._cleanup_routine()
                self._custom_print(f"Job {self.id}: job entry deleted", Msg_level.INFO)
                return
            except Exception as e:
                self._custom_print(e, Msg_level.ERROR)
                self._cleanup_routine()
                time.sleep(5)

        raise RuntimeError("Unable to send job delete request to PS at this moment")
