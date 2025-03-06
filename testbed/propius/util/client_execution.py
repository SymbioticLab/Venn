from propius.client import Client as client_portal
import torch
import copy


class Client:
    def __init__(self, data, config):
        self.data = data
        self.mu = []
        self.std = []

        self._normalize()
        self.x = self.data[:, :-1]
        y = self.data[:, -1]
        self.y = torch.reshape(y, (self.x.shape[0], 1))

        self.weights = []
        self.new_weights = []

        self.config = config
        self.client_portal = client_portal(config, True, False)

    def _normalize(self):
        for i in range(1, self.data.shape[1] - 1):
            mean = torch.mean(self.data[:, i])
            std = torch.std(self.data[:, i])
            self.data[:, i] = (self.data[:, i] - mean) / std
            self.mu.append(mean)
            self.std.append(std)

    def _h(self, x, weights):
        return torch.matmul(x, weights)

    def _cost_function(self, x, y, weights):
        return ((self._h(x, weights) - y).T @ (self._h(x, weights) - y)) / (
            2 * y.shape[0]
        )

    def _gradient_descent(self, x, y, weights, learning_rate=0.1, num_epochs=1):
        m = x.shape[0]
        running_cost = []
        for _ in range(num_epochs):
            h_x = self._h(x, weights)
            d_cost = (1 / m) * (x.T @ (h_x - y))
            weights = weights - (learning_rate) * d_cost
            cost = self._cost_function(x, y, weights)
            running_cost.append(cost)

        return weights, running_cost

    def get(self):
        result = self.client_portal.get()
        meta, data = result
        data[0] = data[0].to(torch.float32)
        self.weights = data
        self.new_weights = []

    def execute(self):
        num_epochs = 10
        learning_rate = 0.1
        new_weights, _ = self._gradient_descent(
            self.x, self.y, copy.deepcopy(self.weights[0]), learning_rate, num_epochs
        )
        self.new_weights = [new_weights]

    def push(self):
        if self.new_weights:
            self.client_portal.push(self.new_weights)
            self.new_weights = []
