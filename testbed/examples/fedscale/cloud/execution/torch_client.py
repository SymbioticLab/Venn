import logging
import math
import time

import torch
from torch.autograd import Variable
from torch.nn import CTCLoss
from fedscale.cloud.execution.client_base import ClientBase
#from fedscale.cloud.execution.optimizers import ClientOptimizer
from fedscale.cloud.internal.torch_model_adapter import TorchModelAdapter
from fedscale.utils.model_test_module import test_pytorch_model
from fedscale.dataloaders.divide_data import select_dataset
class TorchClient(ClientBase):
    """Implements a PyTorch-based client for training and evaluation."""

    def __init__(self, args):
        """
        Initializes a torch client.
        :param args: Job args
        """
        self.args = args
        #self.optimizer = ClientOptimizer()
        self.device = args.cuda_device if args.use_cuda else torch.device(
            'cpu')
        
        self.epoch_train_loss = 1e-4
        self.completed_steps = 0
        self.loss_squared = 0
    
    def train(self, client_data, model, conf):
        """
        Perform a training task.
        :param client_data: client training dataset
        :param model: the framework-specific model
        :param conf: job config
        :return: training results
        """
        client_data = select_dataset(
            rank=conf.rank, partition=client_data,
            batch_size=conf.batch_size, args=conf, isTest=False, collate_fn=None)
        client_id = conf.rank
        logging.info(f"Start to train (CLIENT: {client_id}) ...")
        print(f"Client {client_id}: === Start to train ===")
        tokenizer = conf.tokenizer

        model = model.to(device=self.device)
        model.train()

        trained_unique_samples = min(
            len(client_data.dataset), conf.local_steps * conf.batch_size
        )
        self.global_model = None

        #TODO fedprox
        optimizer = self.get_optimizer(model, conf)
        criterion = self.get_criterion(conf)
        error_type = None

        # NOTE: If one may hope to run fixed number of epochs, instead of iterations,
        # use `while self.completed_steps < conf.local_steps * len(client_data)` instead
        while self.completed_steps < conf.local_steps:
            try:
                self.train_step(client_data, conf, model, optimizer, criterion)
            except Exception as ex:
                error_type = ex
                break

        state_dicts = model.state_dict()
        model_param = {p : state_dicts[p].data.cpu().numpy() for p in state_dicts}
        results = {'client_id' : client_id, 'moving_loss' : self.epoch_train_loss,
                   'trained_size' : self.completed_steps * conf.batch_size,
                   'success' : self.completed_steps == conf.local_steps}
        
        if error_type is None:
            logging.info(f"Training of (CLIENT: {client_id}) completes, {results}")
            print(f"Client {client_id}: === training complete, {results}===")
        else:
            logging.info(f"Training of (CLIENT: {client_id}) failed as {error_type}")
            print(f"Client {client_id}: training failed, {error_type}")

        results['utility'] = math.sqrt(self.loss_squared) * float(trained_unique_samples)
        results['update_weight'] = model_param
        results['wall_duration'] = 0

        return results


    def get_optimizer(self, model, conf):
        #TODO detection and nlp task
        optimizer = torch.optim.SGD(
            model.parameters(), lr=conf.learning_rate,
            momentum=0.9, weight_decay=5e-4
        )
        return optimizer
    
    def get_criterion(self, conf):
        criterion = None
        #TODO voice
        criterion = torch.nn.CrossEntropyLoss(reduction='none').to(device=self.device)
        return criterion
    
    def train_step(self, client_data, conf, model, optimizer, criterion):
        for data_pair in client_data:
            #TODO other task
            (data, target) = data_pair
            print(f"Client {conf.rank}: Input data size {data.size()}, label size {target.size()}")
            data = Variable(data).to(device=self.device)
            target = Variable(target).to(device=self.device)

            output = model(data)
            loss = criterion(output, target)

            loss_list = loss.tolist()
            loss = loss.mean()

            temp_loss = sum(loss_list) / float(len(loss_list))
            self.loss_squared = sum([l**2 for l in loss_list]) / float(len(loss_list))

            print(f"Client {conf.rank}: training step {self.completed_steps}, temp loss {temp_loss}")
            if self.completed_steps < len(client_data):
                if self.epoch_train_loss == 1e-4:
                    self.epoch_train_loss = temp_loss
                else:
                    self.epoch_train_loss = (1. - conf.loss_decay) * \
                        self.epoch_train_loss + \
                            conf.loss_decay * temp_loss
                    
            # ========= Define the backward loss ==============
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()

            # ========= Weight handler ========================
            #TODO optimizer
            # self.optimizer.update_client_weight(
            #     conf, model, self.global_model if self.global_model is not None else None)

            self.completed_steps += 1

            if self.completed_steps == conf.local_steps:
                break

    def test(self, client_data, model, conf):
        """
        Perform a testing task.
        :param client_data: client evaluation dataset
        :param model: the framework-specific model
        :param conf: job config
        :return: testing results
        """
        evalStart = time.time()
        #TODO voice task
        client_dataloader = select_dataset(
            rank=conf.rank, partition=client_data,
            batch_size=conf.test_bsz, args=conf, isTest=True, collate_fn=None)
        criterion = torch.nn.CrossEntropyLoss().to(device=self.device)
        test_loss, acc, acc_5, test_results = test_pytorch_model(conf.rank, model,
                                                                 client_dataloader,
                                                                 device=self.device,
                                                                 criterion=criterion,
                                                                 tokenizer=conf.tokenizer)
        

        print(f"Client {conf.rank}: test_loss {test_loss}, accuracy {acc:.2f}, test_5_accuracy {acc_5:.2f}")
        return test_results
    
    def get_model_adapter(self, model) -> TorchModelAdapter:
        """
        Return framework-specific model adapter.
        :param model: the model
        :return: a model adapter containing the model
        """
        return TorchModelAdapter(model)





    
        
