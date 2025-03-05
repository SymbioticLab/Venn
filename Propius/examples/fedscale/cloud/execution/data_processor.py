import torch
from torch.nn.utils.rnn import pad_sequence

from fedscale.cloud.fllibs import *

def collate(examples):
    if tokenizer._pad_token is None:
        return (pad_sequence(examples, batch_first=True), None)
    return (pad_sequence(examples, batch_first=True, padding_value=tokenizer.pad_token_id), None)

#TODO voice collate fn