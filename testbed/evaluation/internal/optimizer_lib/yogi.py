# Source: 
# https://github.com/SymbioticLab/FedScale/blob/master/fedscale/utils/optimizer/yogi.py

import torch

class YoGi():
    def __init__(self, eta=1e-2, tau=1e-3, beta1=0.9, beta2=0.99):
        self.eta = eta
        self.tau = tau
        self.beta1 = beta1
        self.beta2 = beta2
        self.v_t = []
        self.delta_t = []

    def update(self, gradients):
        update_gradients = []
        for idx, g in enumerate(gradients):
            g_sqr = g**2
            if len(self.v_t) <= idx:
                self.v_t.append(g_sqr)
                self.delta_t.append(g)
            else:
                self.delta_t[idx] = self.beta1 * self.delta_t[idx] \
                                    + (1. - self.beta1) * g
                self.v_t[idx] = self.v_t[idx] - (1. - self.beta2) * g_sqr * \
                                torch.sign(self.v_t[idx] - g_sqr)
                yogi_lr = self.eta / (torch.sqrt(self.v_t[idx]) + self.tau)

                update_gradients.append(yogi_lr * self.delta_t[idx])
        if len(update_gradients) == 0:
            update_gradients = gradients

        return update_gradients
