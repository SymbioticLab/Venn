import torch
from propius.parameter_server.util.commons import Msg_level, Propius_logger
from functools import reduce
import pickle

def base_reduce(a, b, func = torch.Tensor.add):
    """Handler for reduction. Receives a, b, performs reduction on a and b
    a, b should be binary objects.
    """
    if a:
        a = pickle.loads(a)
        b = pickle.loads(b)
        with torch.no_grad():
            for i, x in enumerate(b):
                a[i] = reduce(func, [a[i], x])
            return pickle.dumps(a)
    else:
        return b
        

if __name__ == "__main__":
    base_reduce()