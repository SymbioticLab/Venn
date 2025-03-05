import logging

import grpc

import fedscale.cloud.channels.job_api_pb2_grpc as job_api_pb2_grpc
from propius.controller.channels import propius_pb2
from propius.controller.channels import propius_pb2_grpc
import pickle

MAX_MESSAGE_LENGTH = 1*1024*1024*1024  # 1GB

class ClientConnections(object):
    """"Clients build connections to the cloud aggregator."""

    def __init__(self, 
                 lb_ip:str="", lb_port:int=60000):
        self.base_port = -1
        self.aggregator_address = ""
        self.channel = None
        self.stub = None

        # propius
        self.lb_ip = lb_ip
        self.lb_port = lb_port
        self.lb_channel = None
        self.lb_stub = None

    def connect_to_lb(self):
        self.lb_channel = grpc.insecure_channel(f'{self.lb_ip}:{self.lb_port}')
        self.lb_stub = propius_pb2_grpc.Load_balancerStub(self.lb_channel)
        print(f"Client new: connecting to client manager at {self.lb_ip}:{self.lb_port}")
    
    def close_lb_connection(self):
        self.lb_channel.close()

    def connect_to_server(self):
        logging.info('%%%%%%%%%% Opening grpc connection to ' +
                     self.aggregator_address + ' %%%%%%%%%%')
        self.channel = grpc.insecure_channel(
            '{}:{}'.format(self.aggregator_address, self.base_port),
            options=[
                ('grpc.max_send_message_length', MAX_MESSAGE_LENGTH),
                ('grpc.max_receive_message_length', MAX_MESSAGE_LENGTH),
            ]
        )
        self.stub = job_api_pb2_grpc.JobServiceStub(self.channel)

    def close_server_connection(self):
        logging.info(
            '%%%%%%%%%% Closing grpc connection to the aggregator %%%%%%%%%%')
        self.channel.close()

    

    
    