# -*- coding: utf-8 -*-
import collections
import pickle
import random
import time

import numpy as np
import torch

from argparse import Namespace
import fedscale.cloud.channels.job_api_pb2 as job_api_pb2
from fedscale.cloud.channels.channel_context import ClientConnections
#TODO tensorfloew client
from fedscale.cloud.execution.torch_client import TorchClient
from fedscale.cloud.execution.data_processor import collate #TODO voice collate fn
#TODO RL client
from fedscale.cloud.fllibs import *
from fedscale.dataloaders.divide_data import DataPartitioner, select_dataset

class Executor(object):
    """Abstract class for FedScale executor.

    Args:
        args (dictionary): Variable arguments for fedscale runtime config. 
        defaults to the setup in arg_parser.py

    """

    def __init__(self, args):
        #TODO logger
        model = None
        
        #TODO use init model
        if args.model == "resnet18":
            from fedscale.utils.models.specialized.resnet_speech import resnet18

            model = resnet18(num_classes=outputClass[args.data_set], in_channels=1)

        self.model_adapter = self.get_client_trainer(args).get_model_adapter(model)
        self.args = args
        self.num_executors = args.num_executors
        # ======== env information ========
        self.this_rank = args.this_rank
        self.executor_id = str(self.this_rank)

        # ======== model and data ========
        self.training_sets = self.testing_sets = None

        # ======== channels ========
        self.aggregator_communicator = ClientConnections(
            args.ps_ip, args.ps_port)
        
        # ======== runtime information ========
        self.collate_fn = None
        #self.round = 0
        self.start_run_time = time.time()
        self.recieved_stop_request = False
        self.event_queue = collections.deque()

        #TODO wandb
        self.wandb = None
        super(Executor, self).__init__()

    def get_client_trainer(self, conf):
        """
        Returns a framework-specific client that handles training and evaluation.
        :param conf: job config
        :return: framework-specific client instance
        """
        #TODO tensorflow
        #TODO RLclient
        return TorchClient(conf)
    
    def setup_env(self):
        """Set up experiments environment
        """
        #TODO logging
        self.setup_seed(seed=1)

    def setup_seed(self, seed=1):
        """Set random seed for reproducibility

        Args:
            seed (int): random seed

        """
        torch.manual_seed(seed)
        torch.backends.cudnn.deterministic = True
        torch.cuda.manual_seed_all(seed)
        np.random.seed(seed)
        random.seed(seed)

    def init_data(self):
        """Return the training and testing dataset

        Returns:
            Tuple of DataPartitioner class: The partioned dataset class for training and testing

        """
        #TODO train_dataset, test_dataset = init_dataset()
        if self.args.data_set == "femnist":
            from fedscale.dataloaders.femnist import FEMNIST
            from fedscale.dataloaders.utils_data import get_data_transform

            train_transform, test_transform = get_data_transform('mnist')
            train_dataset = FEMNIST(
                self.args.data_dir, dataset='train', transform=train_transform)
            test_dataset = FEMNIST(
                self.args.data_dir, dataset='test', transform=test_transform)

        #TODO various tasks
        # load data partitionxr (entire_train_data)
        #TODO logging
        training_sets = DataPartitioner(
            data=train_dataset, args=self.args, numOfClass=self.args.num_class)
        #TODO training_sets.partition_data_helper(
        #     num_clients=self.args.num_participants, data_map_file=self.args.data_map_file)
        training_sets.partition_data_helper(
            num_clients=self.args.num_clients, data_map_file=None
        )
        testing_sets = DataPartitioner(
            data=test_dataset, args=self.args, numOfClass=self.args.num_class, isTest=True)
        testing_sets.partition_data_helper(num_clients=self.num_executors)

        #TODO logging

        return training_sets, testing_sets

    def setup_communication(self):
        """Set up grpc connection
        """
        self.init_control_communication()
        self.init_data_communication()

    def init_control_communication(self):
        """Create communication channel between coordinator and executor.
        This channel serves control messages.
        """
        self.aggregator_communicator.connect_to_server()

    def init_data_communication(self):
        """In charge of jumbo data traffics (e.g., fetch training result)
        """
        pass

    def serialize_response(self, responses):
        """Serialize the response to send to server upon assigned job completion

        Args:
            responses (string, bool, or bytes): TorchClient responses after job completion.

        Returns:
            bytes stream: The serialized response object to server.

        """
        return pickle.dumps(responses)
    
    def deserialize_response(self, responses):
        """Deserialize the response from server

        Args:
            responses (byte stream): Serialized response from server.

        Returns:
            ServerResponse defined at job_api.proto: The deserialized response object from server.

        """
        return pickle.loads(responses)
    
    def report_executor_info_handler(self):
        """Return the statistics of training dataset

        Returns:
            none

        """
        return ""
    
    def dispatch_worker_events(self, request):
        """Add new events to worker queues

        Args:
            request (string): Add grpc request from server (e.g. MODEL_TEST, MODEL_TRAIN) to event_queue.

        """
        self.event_queue.append(request)

    def client_register(self):
        """Register the executor information to the aggregator
        """
        start_time = time.time()
        while time.time() - start_time < 180:
            try:
                print(f"Client {self.executor_id}: register to parameter server")
                response = self.aggregator_communicator.stub.CLIENT_REGISTER(
                    job_api_pb2.RegisterRequest(
                        client_id=self.executor_id,
                        executor_id=self.executor_id,
                        executor_info=self.serialize_response(
                            self.report_executor_info_handler()
                        )
                    )
                )
                self.dispatch_worker_events(response)
                break
            except Exception as e:
                print(e)
                #TODO logging warning
                time.sleep(5)

    def UpdateModel(self, model_weights):
        """Receive the broadcasted global model for current round

        Args:
            config (PyTorch or TensorFlow model): The broadcasted global model config

        """
        #self.round += 1
        self.model_adapter.set_weights(model_weights)

    def client_ping(self):
        """Ping the aggregator for new task
        """
        print(f"Client {self.executor_id}: pinging parameter server")
        response = self.aggregator_communicator.stub.CLIENT_PING(job_api_pb2.PingRequest(
            client_id=self.executor_id,
            executor_id=self.executor_id
        ))
        self.dispatch_worker_events(response)

    def Train(self, config):
        """Load train config and data to start training on that client

        Args:
            config (dictionary): The client training config.

        Returns:
            tuple (int, dictionary): The client id and train result

        """
        client_id = config['client_id']
        train_config = config['task_config']

        # if 'model' not in config or not config['model']:
        #     raise "The 'model' object must be a non-null value in the training config."
        
        client_conf = self.override_conf(train_config)
        train_res = self.training_handler(client_id=client_id,
                                          conf=client_conf)
        
        # Report execution completion meta information
        while True:
            try:
                response = self.aggregator_communicator.stub.CLIENT_EXECUTE_COMPLETION(
                    job_api_pb2.CompleteRequest(
                        client_id=str(client_id),
                        executor_id=self.executor_id,
                        event=commons.CLIENT_TRAIN,
                        status=True,
                        msg=None,
                        meta_result=None,
                        data_result=None
                    )
                )
                break
            except Exception as e:
                time.sleep(0.5)

        self.dispatch_worker_events(response)

        return client_id, train_res

    def training_handler(self, client_id, conf):
        """Train model given client id

        Args:
            client_id (int): The client id.
            conf (dictionary): The client runtime config.

        Returns:
            dictionary: The train result

        """
        #self.model_adapter.set_weights(model)
        conf.client_id = client_id
        #TODO conf tokenizer
        #TODO rl training set
        client_data = select_dataset(client_id, self.training_sets,
                                   batch_size=conf.batch_size, 
                                   args=self.args,
                                   collate_fn=self.collate_fn)
        client = self.get_client_trainer(self.args)
        train_res = client.train(client_data=client_data,
                                 model=self.model_adapter.get_model(),
                                 conf = conf)
        return train_res
    
    def testing_handler(self):
        """Test model

        Args:
            args (dictionary): Variable arguments for fedscale runtime config. defaults to the setup in arg_parser.py
            config (dictionary): Variable arguments from coordinator.
        Returns:
            dictionary: The test result

        """
        test_config = self.override_conf({
            'rank': self.this_rank,
            'memory_capacity': self.args.memory_capacity,
            'tokenizer': tokenizer
        })
        client = self.get_client_trainer(test_config)
        data_loader = select_dataset(self.this_rank, self.testing_sets,
                                     batch_size=self.args.
                                     test_bsz, args=self.args,
                                     isTest=True, collate_fn=self.collate_fn)
        test_results = client.test(data_loader, self.model_adapter.get_model(), test_config)
        #TODO log result
        #TODO gc.collect()
        return test_results


    
    def Test(self, config):
        """Model Testing. By default, we test the accuracy on all data of clients in the test group

        Args:
            config (dictionary): The client testing config.

        """
        test_res = self.testing_handler()
        test_res = {'executorId': self.this_rank, 'results': test_res}

        # Report execution completion information
        response = self.aggregator_communicator.stub.CLIENT_EXECUTE_COMPLETION(
            job_api_pb2.CompleteRequest(
                client_id=self.executor_id, executor_id=self.executor_id,
                event=commons.MODEL_TEST, status=True, msg=None,
                meta_result=None, data_result=self.serialize_response(test_res)
            )
        )
        self.dispatch_worker_events(response)


    def event_monitor(self):
        """Activate event handler once receiving new message
        """
        #TODO logging
        self.client_register()

        while not self.recieved_stop_request:
            if len(self.event_queue) > 0:
                request = self.event_queue.popleft()
                current_event = request.event

                if current_event == commons.CLIENT_TRAIN:
                    print(f"Client {self.executor_id}: recieve train event")
                    train_config = self.deserialize_response(request.meta)
                    #train_model = self.deserialize_response(request.data)
                    #train_config['model'] = train_model
                    train_config['client_id'] = int(train_config['client_id'])
                    client_id, train_res = self.Train(train_config)

                    # Upload model updates
                    future_call = self.aggregator_communicator.stub.CLIENT_EXECUTE_COMPLETION.future(
                        job_api_pb2.CompleteRequest(
                        client_id=str(client_id),
                        executor_id=self.executor_id,
                        event=commons.UPLOAD_MODEL,
                        status=True,
                        msg=None,
                        meta_result=None,
                        data_result=self.serialize_response(train_res)
                        )
                    )
                    future_call.add_done_callback(
                        lambda _response: self.dispatch_worker_events(_response.result())
                        )

                elif current_event == commons.MODEL_TEST:
                    print(f"Client {self.executor_id}: recieve test event")
                    self.Test(self.deserialize_response(request.meta))

                elif current_event == commons.UPDATE_MODEL:
                    print(f"Client {self.executor_id}: recieve update model event")
                    model_weights = self.deserialize_response(request.data)
                    self.UpdateModel(model_weights)
                
                elif current_event == commons.SHUT_DOWN:
                    print(f"Client {self.executor_id}: recieve shutdown event")
                    self.recieved_stop_request = True
                    self.Stop()
                
                elif current_event == commons.DUMMY_EVENT:
                    print(f"Client {self.executor_id}: recieve dummy event")
                    pass
            
            else:
                time.sleep(1)
                try:
                    self.client_ping()
                except Exception as e:
                    #TODO logging
                    self.Stop()


    
    def run(self):
        """Start running the executor by setting up execution and communication environment, 
        and monitoring the grpc message.
        """
        print(f"Client {self.executor_id}: setting up environment")
        self.setup_env()
        print(f"Client {self.executor_id}: initting data")
        self.training_sets, self.testing_sets = self.init_data()
        print(f"Client {self.executor_id}: setting up communication")
        self.setup_communication()
        print(f"Client {self.executor_id}: registering to job")
        self.event_monitor()

    def Stop(self):
        """Stop the current executor
        """
        #logging.info(f"Terminating the executor ...")
        #TODO logging
        self.aggregator_communicator.close_sever_connection()
        self.received_stop_request = True
        # if self.wandb != None:
        #     self.wandb.finish()
        #TODO wandb

    def override_conf(self, config):
        """ Override the variable arguments for different client

        Args:
            config (dictionary): The client runtime config.

        Returns:
            dictionary: Variable arguments for client runtime config.

        """
        default_conf = vars(self.args).copy()

        for key in config:
            default_conf[key] = config[key]

        return Namespace(**default_conf)
    

if __name__ == "__main__":
    args = {
        "tokenizer" : None,
        "local_steps": 10,
        "batch_size" : 10,
        "gradient_policy" : "SGD",
        "learning_rate" : 0.05,

        "use_cuda" : False,
        "task" : "cv",
        "model" : "resnet18",
        "data_set": "femnist",
        "num_executors" : 2,
        "num_clients" : 2,
        "this_rank" : 2,
        "ps_ip" : "localhost",
        "ps_port" : 60500,
        "data_dir" : "./benchmark/dataset/data/femnist",
        "num_class" : 0,
        "test_ratio" : 0.5,
        "batch_size" : 10,
        "num_loaders" : 8,
        "memory_capacity" : 1,
        "test_bsz" : 10,
        "loss_decay" : 0.95,
    }
    
    args = Namespace(**args)
    executor = Executor(args)
    executor.run()
