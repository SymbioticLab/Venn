from propius.controller.channels import propius_pb2_grpc
from propius.controller.channels import propius_pb2
import pickle
import grpc
import asyncio
import time
from propius.controller.util.commons import Msg_level, get_time, geq, encode_specs
import logging

def gen_client_config():
    pass

class Propius_client():
    def __init__(self, client_config: dict, verbose: bool = False, logging: bool = False):
        """Init Propius_client class

        Args:
            client_config:
                public_specifications: dict
                private_specifications: dict
                load_balancer_ip
                load_balancer_port
                option: float
            verbose: whether to print or not
            logging: whether to log or not

        Raises:
            ValueError: input key not recognized | missing key
        """

        self.id = -1
        # TODO arguments check
        # TODO add state flow check
        public, private = encode_specs(**client_config['public_specifications'], **client_config['private_specifications'])
        self.public_specifications = tuple(public)
        self.private_specifications = tuple(private)
        self.option = client_config['option'] if 'option' in client_config else 0

        self._lb_ip = client_config['load_balancer_ip']
        self._lb_port = client_config['load_balancer_port']
        self._lb_channel = None
        self._lb_stub = None

        self.verbose = verbose
        self.logging = logging
        
    def _cleanup_routine(self):
        try:
            self._lb_channel.close()
        except Exception:
            pass

    def __del__(self):
        self._cleanup_routine()

    def _custom_print(self, message: str, level: int=Msg_level.PRINT):
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
        
    def _connect_lb(self) -> None:
        self._lb_channel = grpc.insecure_channel(f'{self._lb_ip}:{self._lb_port}')
        self._lb_stub = propius_pb2_grpc.Load_balancerStub(self._lb_channel)

        self._custom_print(f"Client: connecting to load balancer at {self._lb_ip}:{self._lb_port}")

    def connect(self, num_trial: int=1):
        """Connect to Propius load balancer

        Args: 
            num_trial: number of connection attempt, default to 1

        Raise:
            RuntimeError: if can't establish connection after multiple trial
        """

        for _ in range(num_trial):
            try:
                self._connect_lb()
                self._custom_print(f"Client: connected to Propius")
                return
            except Exception as e:
                self._custom_print(e, Msg_level.ERROR)
                time.sleep(2)

        raise RuntimeError(
            "Unable to connect to Propius at the moment")
    
    def close(self) -> None:
        """Clean up allocation, close connection to Propius
        """

        self._cleanup_routine()
        self._custom_print(f"Client {self.id}: closing connection to Propius")

    def client_check_in(self, num_trial: int=1) -> tuple[list, list]:
        """Client check in. Send client public spec to Propius client manager. Propius will return task offer list for client to select a task locally.

        Args:
            num_trial: number of connection attempt, default to 1

        Returns:
            task_ids: list of task ids
            task_private_constraint: list of tuple of private constraint of the corresponding task in task_ids
        
        Raises: 
            RuntimeError: if can't establish connection after multiple trial
        """

        for _ in range(num_trial):
            info = {
                "ps": self.public_specifications,
                "op": self.option
            }
            client_checkin_msg = propius_pb2.client_checkin(
                public_specification=pickle.dumps(info)
            )
            try:
                cm_offer = self._lb_stub.CLIENT_CHECKIN(client_checkin_msg)
                self.id = cm_offer.client_id
                task_ids = pickle.loads(cm_offer.task_offer)
                task_private_constraint = pickle.loads(
                    cm_offer.private_constraint)
                
                self._custom_print(f"Client {self.id}: checked in to Propius, public spec {self.public_specifications}")
                return (task_ids, task_private_constraint)
            
            except Exception as e:
                self._custom_print(e, Msg_level.ERROR)
                time.sleep(2)
        raise RuntimeError("Unable to connect to Propius at the moment")
    
    def client_ping(self, num_trial: int=1) -> tuple[list, list]:
        """Client ping. Propius will return task offer list for client to select a task locally. Note that this function should only be called after client_check_in fails.

        Args:
            num_trial: number of connection attempt, default to 1

        Returns:
            task_ids: list of task ids
            task_private_constraint: list of tuple of private constraint of the corresponding task in task_ids
        
        Raises: 
            RuntimeError: if can't establish connection after multiple trial
        """

        for _ in range(num_trial):
            try:
                cm_offer = self._lb_stub.CLIENT_PING(propius_pb2.client_id(id=self.id))
                task_ids = pickle.loads(cm_offer.task_offer)
                task_private_constraint = pickle.loads(
                    cm_offer.private_constraint)
                self._custom_print(f"Client {self.id}: pinged Propius")
                return (task_ids, task_private_constraint)
            
            except Exception as e:
                self._custom_print(e, Msg_level.ERROR)
                time.sleep(2)
        
        raise RuntimeError("Unable to connect to Propius at the moment")
    
    def select_task(self, task_ids: list, private_constraints: list)->int:
        """Client select a task locally. The default strategy is to select the first task in task offer list of which the private constraint is satisfied by the client private specs. 

        Args:   
            task_ids: list of task id
            private_constraint: list of tuples of task private constraint

        Returns:
            task_id: id of task, -1 if no suitable task is found
        """

        for idx, task_id in enumerate(task_ids):
            if len(
                    self.private_specifications) != len(
                    private_constraints[idx]):
                raise ValueError(
                    "client private specification len does not match required")
            if geq(self.private_specifications, private_constraints[idx]):
                self._custom_print(f"Client {self.id}: select task {task_id}")
                return task_id

        self._custom_print(f"Client {self.id}: not eligible")
        return -1
    
    def client_accept(self, task_id: int, num_trial: int=1)->tuple[str, int, int]:
        """Client send task id of the selected task to Propius. Returns address of the selected job parameter server if successful, None otherwise

        Args:
            task_id: id of the selected task
            num_trial: number of connection attempt, default to 1

        Returns:
            ack: a boolean indicating whether the task selected is available for the client.
            ps_ip: ip address of the selected job parameter server
            ps_port: port number of the selected job parameter server
            round: current round number
        Raises: 
            RuntimeError: if can't establish connection after multiple trial
        """

        for _ in range(num_trial):
            client_accept_msg = propius_pb2.client_accept(
                client_id=self.id, task_id=task_id
            )
            try:
                cm_ack = self._lb_stub.CLIENT_ACCEPT(client_accept_msg)
                if cm_ack.ack:
                    self._custom_print(f"Client {self.id}: client task selection is received")
                    return (pickle.loads(cm_ack.job_ip), cm_ack.job_port, cm_ack.round)
                else:
                    self._custom_print(f"Client {self.id}: client task selection is rejected", Msg_level.WARNING)
                    return None
            
            except Exception as e:
                self._custom_print(e, Msg_level.ERROR)
                time.sleep(2)
        
        raise RuntimeError("Unable to connect to Propius at the moment")

    def auto_assign(self, ttl:int=3)->tuple[int, bool, int, str, int, int]:
        """Automate client register, client ping, and client task selection process

        Args:
            ttl: number of attempts to inquire Propius for task offer until client is scheduled

        Returns:
            client_id: client id assigned by Propius
            status: a boolean indicating whether the client is assigned
            task_id: task id
            ps_ip: job parameter server ip address
            ps_port: job parameter server port address
            round: current task round
        Raises:
            RuntimeError: if can't establish connection after multiple trial
        """

        ttl = min(ttl, 10)
        task_ids, task_private_constraint = self.client_check_in()
        while ttl > 0:
            while ttl > 0:
                if len(task_ids) > 0:
                    break
                time.sleep(2)
                ttl -= 1
                task_ids, task_private_constraint = self.client_ping()

            if len(task_ids) == 0:
                break
            
            self._custom_print(
                f"Client {self.id}: receive client manager offer: {task_ids}")
            
            task_id = self.select_task(task_ids, task_private_constraint)
            self._custom_print(f"Client {self.id}: {task_id} selected", Msg_level.INFO)

            if task_id == -1:
                task_ids, task_private_constraint = [], []
                continue

            result = self.client_accept(task_id)

            if not result:
                self._custom_print(f"Client {self.id}: {task_id} not accepted", Msg_level.INFO)
                task_ids, task_private_constraint = [], []
                continue
            else:
                self._custom_print(f"Client {self.id}: scheduled with {task_id}", Msg_level.INFO)
                return (self.id, True, task_id, result[0], result[1], result[2])
            
        return (self.id, False, -1, None, -1, -1)
    


