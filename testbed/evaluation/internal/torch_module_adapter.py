# Source
# https://github.com/SymbioticLab/FedScale/blob/master/fedscale/cloud/internal/torch_model_adapter.py

from typing import List
import numpy as np
import torch
import copy
from evaluation.internal.optimizers import TorchServerOptimizer
from evaluation.commons import *

class Torch_model_adapter:
    def __init__(self, model: torch.nn.Module, optimizer: TorchServerOptimizer):
        """
        Initializes a TorchModelAdapter.
        :param model: the PyTorch model to adapt
        :param optimizer: the optimizer to apply weights, when specified.
        """
        self.model = model
        self.optimizer = optimizer

    def set_weights(self, weights):
        """
        Set the model's weights to the numpy weights array.
        :param weights: numpy weights array
        """
        last_weights = [param.data.clone() for param in self.model.state_dict().values()]
        new_weights = copy.deepcopy(weights)
        self.optimizer.update_round_gradient(last_weights,
                                            new_weights,
                                            self.model,
                                            )

    def get_weights(self)-> List[np.ndarray]:
        return [params.data.clone() for params in self.model.state_dict().values()]
    
    def get_model(self):
        return self.model