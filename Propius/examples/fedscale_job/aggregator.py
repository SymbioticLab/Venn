# -*- coding: utf-8 -*-
import sys
[sys.path.append(i) for i in ['.', '..', '...']]
import collections
import copy
import math
import os
import pickle
import random
import threading
import time
from concurrent import futures

import grpc
import numpy as np
import torch
#TODO import wandb

import examples.fedscale.cloud.channels.job_api_pb2_grpc as job_api_pb2_grpc
from examples.fedscale.cloud.channels import job_api_pb2
from examples.fedscale.cloud.aggregation.optimizers import TorchServerOptimizer
from examples.fedscale.cloud.internal.torch_model_adapter import TorchModelAdapter
from examples.fedscale.cloud.fllibs import *

from argparse import Namespace
import yaml
from propius_controller.channels import propius_pb2
from propius_controller.channels import propius_pb2_grpc
import sys


MAX_MESSAGE_LENGTH = 1 * 1024 * 1024 * 1024  # 1GB

class Aggregator(job_api_pb2_grpc.JobServiceServicer):
    """This centralized aggregator collects training/testing feedbacks from executors

    Args:
        args (dictionary): Variable arguments for fedscale runtime config. defaults to the setup in arg_parser.py

    """

    def __init__(self, gconfig, args):
        self.args = args
        #TODO deployment
        self.experiment_mode = 'deployment'
        self.device = 'cpu'

        # ======== env information ========
        #TODO virtual clock
        #TODO resource manager/client manager

        # ======== model and data ========
        self.model_wrapper = None
        self.model_in_update = 0
        self.update_lock = threading.Lock()
        # all weights including bias/#_batch_tracked (e.g., state_dict)
        self.model_weights = None
        #TODO model saving

        # ======== channels ========
        self.connection_timeout = self.args.connection_timeout
        self.grpc_server = None

        # ======== Event Queue =======
        self.individual_client_events = {}  # Unicast
        self.server_events_queue = collections.deque()
        self.broadcast_events_queue = collections.deque()  # Broadcast

        # ======== runtime information ========
        self.tasks_round = self.args.demand
        #TODO self.round_stragglers = []
        self.model_update_size = 0.

        self.collate_fn = None
        self.round = 1
        self.total_round = self.args.total_round

        self.start_run_time = time.time()
        self.client_conf = {}
        
        #TODO self.stats_util_accumulator = []
        self.loss_accumulator = []

        # number of registered executors
        #TODO self.registered_executor_info = set()
        self.test_result_accumulator = []
        #TODO testing history
        #TODO log
        #TODO wandb
        #TODO init task context

        # ======== propius =======
        self.id = -1
        self.jm_channel = None
        self.jm_stub = None
        jm_ip = gconfig['job_manager_ip']
        jm_port = gconfig['job_manager_port']
        self._connect_jm(jm_ip, jm_port)

        self.public_constraint = tuple(args.public_constraint)
        self.private_constraint = tuple(args.private_constraint)
        self.ip = args.ps_ip
        self.port = args.ps_port
        self.shut_down = False

        self.execution_start = False

    def _connect_jm(self, jm_ip:str, jm_port:int)->None:
        self.jm_channel = grpc.insecure_channel(f'{jm_ip}:{jm_port}')
        self.jm_stub = propius_pb2_grpc.Job_managerStub(self.jm_channel)
        print(f"Aggregator: connecting to job manager at {jm_ip}:{jm_port}")

    def setup_env(self):
        """Set up experiments environment and server optimizer
        """
        self.setup_seed(seed=1)

    def setup_seed(self, seed=1):
        """Set global random seed for better reproducibility

        Args:
            seed (int): random seed

        """
        torch.manual_seed(seed)
        torch.cuda.manual_seed_all(seed)
        np.random.seed(seed)
        random.seed(seed)
        torch.backends.cudnn.deterministic = True

    def init_control_communication(self):
        """Create communication channel between coordinator and executor.
        This channel serves control messages.
        """
        #TODO logging
        #TODO self executors

        # initiate a server process
        self.grpc_server = grpc.server(
            futures.ThreadPoolExecutor(max_workers=20),
            options=[
                ('grpc.max_send_message_length', MAX_MESSAGE_LENGTH),
                ('grpc.max_receive_message_length', MAX_MESSAGE_LENGTH),
            ],
        )

        job_api_pb2_grpc.add_JobServiceServicer_to_server(
            self, self.grpc_server)
        port = f"{self.args.ps_ip}:{self.args.ps_port}"
        #TODO logging
        self.grpc_server.add_insecure_port(port)
        self.grpc_server.start()

    def init_model(self):
        """Initialize the model"""
        #TODO tensorflow
        if self.args.engine == commons.PYTORCH:
            if args.model == "resnet18":
                from fedscale.utils.models.specialized.resnet_speech import resnet18

                model = resnet18(num_classes=outputClass[args.data_set], in_channels=1)
                self.model_wrapper = TorchModelAdapter(model, 
                                                       optimizer=TorchServerOptimizer(
                    self.args.gradient_policy, self.args, self.device))
                self.model_weights = self.model_wrapper.get_weights()

    def dispatch_client_events(self, event, clients=None):
        """Issue tasks (events) to clients

        Args:
            event (string): grpc event (e.g. MODEL_TEST, MODEL_TRAIN) to event_queue.
            clients (list of int): target client ids for event.

        """

        for individual_event_queue in self.individual_client_events.values():
            individual_event_queue.append(event)

    def client_completion_handler(self, results):
        """We may need to keep all updates from clients,
        if so, we need to append results to the cache

        Args:
            results (dictionary): client's training result

        """
        # Format:
        #       -results = {'client_id':client_id, 'update_weight': model_param, 'moving_loss': round_train_loss,
        #       'trained_size': count, 'wall_duration': time_cost, 'success': is_success 'utility': utility}

        #TODO q-fedavg
        #TODO stats
        self.loss_accumulator.append(results['moving_loss'])
        #TODO client manager register feedback

        # ================== Aggregate weights ======================
        self.update_lock.acquire()

        self.model_in_update += 1
        self.update_weight_aggregation(results)

        self.update_lock.release()

    def _is_first_result_in_round(self):
        return self.model_in_update == 1
    
    def _is_last_result_in_round(self):
        return self.model_in_update == self.tasks_round

    def update_weight_aggregation(self, results):
        """Updates the aggregation with the new results.

        :param results: the results collected from the client.
        """
        update_weights = results['update_weight']
        if type(update_weights) is dict:
            update_weights = [x for x in update_weights.values()]
        if self._is_first_result_in_round:
            self.model_weights = update_weights
        else:
            self.model_weights = [weight + update_weights[i] 
                                  for i, weight in enumerate(self.model_weights)]
        if self._is_last_result_in_round():
            self.model_weights = [np.divide(weight, self.tasks_round)
                                  for weight in self.model_weights]
            self.model_wrapper.set_weights(copy.deepcopy(self.model_weights))

    def deserialize_response(self, responses):
        """Deserialize the response from executor

        Args:
            responses (byte stream): Serialized response from executor.

        Returns:
            string, bool, or bytes: The deserialized response object from executor.
        """
        return pickle.loads(responses)
    
    def broadcast_aggregator_events(self, event):
        """Issue tasks (events) to aggregator worker processes by adding grpc request event
        (e.g. MODEL_TEST, MODEL_TRAIN) to event_queue.

        Args:
            event (string): grpc event (e.g. MODEL_TEST, MODEL_TRAIN) to event_queue.

        """
        self.broadcast_events_queue.append(event)
    
    def round_start_handler(self):
        run_time = time.time() - self.start_run_time
        print(f"Wall clock: {run_time} s, starting round: {self.round}, Planned participants: " + 
              f"{len(self.individual_client_events)}")
        self.update_default_task_config()
        if self.round % self.args.eval_interval == 0 or self.round == 1:
            self.broadcast_aggregator_events(commons.UPDATE_MODEL)
            self.broadcast_aggregator_events(commons.MODEL_TEST)
        else:
            self.broadcast_aggregator_events(commons.UPDATE_MODEL)
            self.broadcast_aggregator_events(commons.START_ROUND)
        
    
    def round_completion_handler(self):
        """Triggered upon the round completion, it registers the last round execution info,
        broadcast new tasks for executors and select clients for next round.
        """
        #TODO virtual clock
        #TODO stats
        #TODO client manager register feedback for straggler
        avg_loss = sum(self.loss_accumulator) / max(1, len(self.loss_accumulator))
        #TODO logging
        run_time = time.time() - self.start_run_time
        print(f"Wall clock: {run_time} s, ending round: {self.round}, number of results: " + 
              f"{len(self.loss_accumulator)}, Training loss: {avg_loss}")
        
        #TODO dump round completion information to tensorboard
        #TODO update select participants
        #TODO tiktak client tasks

        #TODO logging
        #TODO issue requests to resource manager

        # Update executors and participants
        #TODO simulation
        #TODO other simulation data
        self.individual_client_events = {}
        self.model_in_update = 0
        self.test_result_accumulator = []
        self.loss_accumulator = []
        self.round += 1
        

    def update_default_task_config(self):
        """Update the default task configuration after each round
        """
        if self.round % self.args.decay_round == 0:
            self.args.learning_rate = max(
                self.args.learning_rate * self.args.decay_factor, self.args.min_learning_rate)
    
    def aggregate_test_result(self):
        accumulator = self.test_result_accumulator[0]
        for i in range(1, len(self.test_result_accumulator)):
            #TODO: detection
            for key in accumulator:
                accumulator[key] += self.test_result_accumulator[i][key]
        #TODO testing history
        avg_loss = 0
        for metric_name in accumulator.keys():
            if metric_name == 'test_loss':
                avg_loss = accumulator['test_loss'] / accumulator['test_len']
            #TODO other metric

        print(f"Parameter server {self.id}: round {self.round} avg loss: {avg_loss}")
    def testing_completion_handler(self, client_id, results):
        """Each executor will handle a subset of testing dataset

        Args:
            client_id (int): The client id.
            results (dictionary): The client test results.

        """
        results = results['results']

        # List append is thread-safe
        self.test_result_accumulator.append(results)

        # Have collected all testing results
        if len(self.test_result_accumulator) >= self.tasks_round:
            self.aggregate_test_result()
            #TODO dump test result
            #TODO save model
            #TODO logging
            self.broadcast_events_queue.append(commons.START_ROUND)


    def event_monitor(self):
        """Activate event handler according to the received new message
        """
        while not self.shut_down:
            # Broadcast events to clients
            if len(self.broadcast_events_queue) > 0:
                current_event = self.broadcast_events_queue.popleft()

                if current_event in (commons.UPDATE_MODEL, commons.MODEL_TEST):
                    self.dispatch_client_events(current_event)

                elif current_event == commons.START_ROUND:
                    self.dispatch_client_events(commons.CLIENT_TRAIN)

                elif current_event == commons.SHUT_DOWN:
                    self.dispatch_client_events(commons.SHUT_DOWN)
                    #TODO edit logic for deployment
            
            # Handle events queued on the aggregator
            elif len(self.server_events_queue) > 0:
                client_id, current_event, _, data = self.server_events_queue.popleft()

                if current_event == commons.UPLOAD_MODEL:
                    self.client_completion_handler(
                        self.deserialize_response(data))
                    if len(self.loss_accumulator) >= self.tasks_round:
                        self.round_completion_handler()
                        if self.round > self.args.rounds:
                            self.shut_down = True
                        else:
                            if not self.request():
                                self.shut_down = True
                                return
                
                elif current_event == commons.MODEL_TEST:
                    self.testing_completion_handler(
                        client_id, self.deserialize_response(data))
                    
                else:
                    #TODO logging
                    pass
            
            else:
                # execute every 100 ms
                time.sleep(0.1)

    def client_register_handler(self, executor_id, info):
        """Triggered once receive new executor registration.

        Args:
            executorId (int): Executor Id
            info (dictionary): Executor information

        """
        pass

    def request(self)->bool:
        request_msg = propius_pb2.job_round_info(
            id = self.id,
            demand = self.tasks_round,
        )

        self.execution_start = False
        ack_msg = self.jm_stub.JOB_REQUEST(request_msg)
        if not ack_msg.ack:
            print(f"Parameter server {self.id}: round {self.round}/{self.total_round} request failed")
            return False
        else:
            print(f"Parameter server {self.id}: round {self.round}/{self.total_round} request success")
            return True
        
    def end_request(self)->bool:
        """optional, terminating request"""
        request_msg = propius_pb2.job_id(id=self.id)
        ack_msg = self.jm_stub.JOB_END_REQUEST(request_msg)
        if not ack_msg.ack:
            print(f"Job {self.id}: round: {self.round}/{self.total_round} end request failed")
            return False
        else:
            print(f"Job {self.id}: round: {self.round}/{self.total_round} end request")
            return True

    def executor_info_handler(self, executor_id, info):
        """Handler for register executor info and it will start the round after number of
        executor reaches requirement.

        Args:
            executorId (int): Executor Id
            info (dictionary): Executor information

        """
        #TODO logging
        print(f"Parameter server {self.id}: recieve client {executor_id} registration, {len(self.individual_client_events)} over {self.tasks_round} registered")

        #TODO simulation
        #TODO self.client_register_handler(executor_id, info)
        if len(self.individual_client_events) >= self.tasks_round:
            self.round_start_handler()

    def CLIENT_REGISTER(self, request, context):
        """FL TorchClient register to the aggregator

        Args:
            request (RegisterRequest): Registeration request info from executor.

        Returns:
            ServerResponse: Server response to registeration request

        """
        dummy_data = self.serialize_response(commons.DUMMY_RESPONSE)
        event=commons.DUMMY_EVENT
        executor_id = request.executor_id
        executor_info = self.deserialize_response(request.executor_info)
        if len(self.individual_client_events) >= self.tasks_round or self.round > self.total_round:
            # Check in later
            event=commons.SHUT_DOWN
            print(f"Parameter server {self.id}: recieve client {executor_id} register during round, check in later")
        else:
            print(f"Parameter server {self.id}: recieve client {executor_id} register")
            if executor_id not in self.individual_client_events:
                #TODO logging
                self.individual_client_events[executor_id] = collections.deque()
                self.executor_info_handler(executor_id, executor_info)
        if len(self.individual_client_events) >= self.tasks_round:
            if not self.execution_start:
                self.end_request()
                self.execution_start = True
        return job_api_pb2.ServerResponse(event=event,
                                          meta=dummy_data, data=dummy_data)
    

    def get_client_conf(self):
        """Training configurations that will be applied on clients,
        developers can further define personalized client config here.

        Args:
            client_id (int): The client id.

        Returns:
            dictionary: TorchClient training config.

        """
        conf = {
            "local_steps": self.args.local_steps,
            "learning_rate": self.args.learning_rate,
            "use_cuda": self.args.use_cuda,
            "num_loaders": self.args.num_loaders,
            "tokenizer": None,
            "local_setps": self.args.local_steps,
            "loss_decay": self.args.loss_decay,
            "batch_size": self.args.batch_size,
        }
        return conf
    
    def create_client_task(self, executor_id):
        """Issue a new client training task to specific executor

        Args:
            executorId (int): Executor Id.

        Returns:
            tuple: Training config for new task. (dictionary, PyTorch or TensorFlow module)

        """
        #TODO get next task
        config = self.get_client_conf()
        # return train_config, self.model_wrapper.get_weights()
        return config
    
    def get_client_test_conf(self):
        """Testing configurations that will be applied on clients,
        developers can further define personalized client config here.

        Args:
            client_id (int): The client id.

        Returns:
            dictionary: TorchClient training config.

        """
        conf = {
            "test_bsz": self.args.test_bsz,
            "use_cuda": self.args.use_cuda,
            "num_loaders": self.args.num_loaders,
            "tokenizer": None,
            "test_ratio": self.args.test_ratio,
        }
        return conf
    
    def get_test_config(self, client_id):
        """FL model testing on clients, developers can further define personalized client config here.

        Args:
            client_id (int): The client id.

        Returns:
            dictionary: The testing config for new task.

        """
        config = self.get_client_test_conf()
        return config
    
    def get_shutdown_config(self, client_id):
        """Shutdown config for client, developers can further define personalized client config here.

        Args:
            client_id (int): TorchClient id.

        Returns:
            dictionary: Shutdown config for new task.

        """
        return {'client_id': client_id}
    
    def serialize_response(self, responses):
        """ Serialize the response to send to server upon assigned job completion

        Args:
            responses (ServerResponse): Serialized response from server.

        Returns:
            bytes: The serialized response object to server.

        """
        return pickle.dumps(responses)
    
    def get_model_config(self):
        """FL model config

        Args:
        Returns:
            dictionary: The model config
        """
        config = {
            "model": self.args.model,
            "use_cuda": self.args.use_cuda,
            "data_set": self.args.data_set,
        }
        return config

    
    def CLIENT_PING(self, request, context):
        """Handle client ping requests

        Args:
            request (PingRequest): Ping request info from executor.

        Returns:
            ServerResponse: Server response to ping request

        """
        executor_id = request.executor_id
        response_data = response_msg = commons.DUMMY_RESPONSE
        if executor_id not in self.individual_client_events:
            current_event = commons.SHUT_DOWN
        elif len(self.individual_client_events[executor_id]) == 0:
            current_event = commons.DUMMY_EVENT
        else:
            current_event = self.individual_client_events[executor_id].popleft()
            if current_event == commons.CLIENT_TRAIN:
                response_msg = self.create_client_task(
                    executor_id)
                #TODO sanity
            elif current_event == commons.MODEL_TEST:
                response_msg = self.get_test_config(executor_id)
            elif current_event == commons.UPDATE_MODEL:
                response_data = self.model_wrapper.get_weights()
                response_msg = self.get_model_config()
            elif current_event == commons.SHUT_DOWN:
                response_msg = self.get_shutdown_config(executor_id)
                if executor_id in self.individual_client_events:
                    del self.individual_client_events[executor_id]

        response_msg, response_data = self.serialize_response(
            response_msg), self.serialize_response(response_data)
        
        response = job_api_pb2.ServerResponse(event=current_event,
                                              meta=response_msg, data=response_data)
        #TODO logging
        if current_event != commons.DUMMY_EVENT:
            print(f"Parameter server {self.id}: issue event ({current_event}) to executor ({executor_id})")
        return response
    
    def add_event_handler(self, client_id, event, meta, data):
        """ Due to the large volume of requests, we will put all events into a queue first.

        Args:
            client_id (int): The client id.
            event (string): grpc event MODEL_TEST or UPLOAD_MODEL.
            meta (dictionary or string): Meta message for grpc communication, could be event.
            data (dictionary): Data transferred in grpc communication, could be model parameters, test result.

        """
        self.server_events_queue.append((client_id, event, meta, data))
    
    def CLIENT_EXECUTE_COMPLETION(self, request, context):
        """FL clients complete the execution task.

        Args:
            request (CompleteRequest): Complete request info from executor.

        Returns:
            ServerResponse: Server response to job completion request

        """

        executor_id, client_id, event = request.executor_id, request.client_id, request.event
        execution_status, execution_msg = request.status, request.msg
        meta_result, data_result = request.meta_result, request.data_result
        print(f"Parameter server {self.id}: recieve client {executor_id} event ({event}) completion")

        current_event = commons.SHUT_DOWN
        response_data = response_msg = commons.DUMMY_RESPONSE
        response_msg = self.serialize_response(response_msg)
        response_data = self.serialize_response(response_data)
        response = job_api_pb2.ServerResponse(event=current_event,
                                              meta=response_msg, data=response_data)

        if event == commons.CLIENT_TRAIN:
            if execution_status is False:
                print(f"Parameter server {self.id}: client {executor_id} fails to complete train")
                if executor_id in self.individual_client_events:
                    del self.individual_client_events[executor_id] 
            else:
                response = self.CLIENT_PING(request, context)
            #TODO resource manager assign new task
        elif event == commons.UPLOAD_MODEL:
            self.add_event_handler(
                executor_id, event, meta_result, data_result
            )
            if executor_id in self.individual_client_events:
                del self.individual_client_events[executor_id] 
        elif event == commons.MODEL_TEST:
            self.add_event_handler(
                executor_id, event, meta_result, data_result
            )
            response = self.CLIENT_PING(request, context)
        else:
            print(f"Parameter server {self.id}: recieved undefined event {event} from client {executor_id}")
            if executor_id in self.individual_client_events:
                del self.individual_client_events[executor_id] 
        return response

    def register(self)->bool:
        job_info_msg = propius_pb2.job_info(
            est_demand = self.tasks_round,
            est_total_round = self.total_round,
            public_constraint = pickle.dumps(self.public_constraint),
            private_constraint = pickle.dumps(self.private_constraint),
            ip = pickle.dumps(self.ip),
            port = self.port,
        )
        ack_msg = self.jm_stub.JOB_REGIST(job_info_msg)
        self.id = ack_msg.id
        ack = ack_msg.ack
        if not ack:
            print(f"Parameter server {self.id}: {self.id}: Propius register failed")
            return False
        else:
            print(f"Parameter server {self.id}: {self.id}: Propius register success")
            return True

    def run(self):
        """Start running the aggregator server by setting up execution
        and communication environment, and monitoring the grpc message.
        """
        if not self.register():
            self.stop()
            return
        self.setup_env()
        #TODO load client profile
        print(f"Parameter server {self.id}: init control communication")
        self.init_control_communication()
        #TODO init data communication
        print(f"Parameter server {self.id}: init model")
        self.init_model()
        self.model_update_size = sys.getsizeof(
            pickle.dumps(self.model_wrapper)) / 1024.0 * 8.
        print(f"Parameter server {self.id}: init model complete, size {self.model_update_size}")
        
        if not self.request():
            self.stop()
            return
        self.event_monitor()
        self.stop()

    def complete_job(self):
        req_msg = propius_pb2.job_id(id=self.id)
        self.jm_stub.JOB_FINISH(req_msg)
    
    def stop(self):
        """Stop the aggregator
        """
        #TODO: logging
        #TODO: wandb
        try:
            self.complete_job()
            self.jm_channel.close()
        except:
            pass
        time.sleep(1)

if __name__ == "__main__":
    global_setup_file = './propius/global_config.yml'

    if len(sys.argv) != 2:
        print("Wrong format: python propius/job/aggregator.py <config file>")
        exit(1)

    with open(global_setup_file, 'r') as gyamlfile:
        try:
            gconfig = yaml.load(gyamlfile, Loader=yaml.FullLoader)
            config_file = str(sys.argv[1])
            with open(config_file, 'r') as config_file:
                args = yaml.load(config_file, Loader=yaml.FullLoader)
                print("Parameter server reads config successfully")
    
                args = Namespace(**args)
                aggregator = Aggregator(gconfig, args)
                try:
                    aggregator.run()
                except Exception as e:
                    raise e
                finally:
                    aggregator.stop()
                    
        except KeyboardInterrupt:
            pass
        except Exception as e:
            print(e)