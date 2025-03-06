# Source:
# https://github.com/SymbioticLab/FedScale/blob/master/fedscale/cloud/aggregation/optimizers.py

import numpy as np
import torch
from evaluation.commons import *

class TorchServerOptimizer:
    """This is a abstract server optimizer class
    
    Args:
        mode (string): mode of gradient aggregation policy
        args (distionary): Variable arguments for fedscale runtime config. defaults to the setup in arg_parser.py
        device (string): Runtime device type
        sample_seed (int): Random seed

    """
    def __init__(self, mode, args, device, sample_seed=233):

        self.mode = mode
        self.args = args
        self.device = device

        if mode == 'fed-yogi':
            from evaluation.internal.optimizer_lib.yogi import YoGi
            self.gradient_controller = YoGi(
                eta=args['yogi_eta'], tau=args['yogi_tau'], beta1=args['yogi_beta1'], beta2=args['yogi_beta2'])
            
    def update_round_gradient(self, last_model, current_model, target_model):
        """ update global model based on different policy
        
        Args:
            last_model (list of tensor weight): A list of global model weight in last round.
            current_model (list of tensor weight): A list of global model weight / updates in this round.
            target_model (PyTorch or TensorFlow nn module): Aggregated model.
        
        """
        if self.mode == 'fed-yogi':
            """
            "Adaptive Federated Optimizations", 
            Sashank J. Reddi, Zachary Charles, Manzil Zaheer, Zachary Garrett, Keith Rush, Jakub Konecný, Sanjiv Kumar, H. Brendan McMahan,
            ICLR 2021.
            """
            current_model = [torch.tensor(x) for x in current_model]
            last_model = [x.to(device=self.device) for x in last_model]
            current_model = [x.to(device=self.device) for x in current_model]

            diff_weight = self.gradient_controller.update(
                [pb-pa for pa, pb in zip(last_model, current_model)])

            new_state_dict = {
                name: last_model[idx] + diff_weight[idx]
                for idx, name in enumerate(target_model.state_dict().keys())
            }
            target_model.load_state_dict(new_state_dict)
        
        elif self.mode == 'q-fedavg':    
            hs = current_model[1] # scalar
            Deltas = current_model[0] # tensor

            Deltas = [x.to(device=self.device) for x in Deltas]

            new_state_dict = {
                name: last_model[idx] - Deltas[idx] / (hs)
                for idx, name in enumerate(target_model.state_dict().keys())
            }
            target_model.load_state_dict(new_state_dict)

        else:
            # fed-avg, fed-prox
            current_model = [torch.tensor(x) for x in current_model]
            new_state_dict = {
                name: current_model[i] for i, name in enumerate(target_model.state_dict().keys())
            }
            target_model.load_state_dict(new_state_dict)