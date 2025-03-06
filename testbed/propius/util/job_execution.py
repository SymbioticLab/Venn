from propius.job import Job as job_portal
import torch


class Job:
    def __init__(self, data, model, config):
        self.model = model
        self.test_data = data

        self.config = config
        self.job_portal = job_portal(config, True, False)

        self._normalize()
        self.x = self.test_data[:, :-1]
        y = self.test_data[:, -1]
        self.y = torch.reshape(y, (self.x.shape[0], 1))


    def register(self):
        self.job_portal.register()

    def request(self):
        weights = self.model["weights"]
        self.job_portal.request({}, data=[weights])

    def update(self):
        _, aggregation = self.job_portal.reduce()
        new_weights = aggregation[0]

        num_client = self.config["demand"]
        self.model["weights"] = new_weights / num_client

    def complete(self):
        self.job_portal.complete()

    def _normalize(self):
        for i in range(1, self.test_data.shape[1] - 1):
            mean = torch.mean(self.test_data[:, i])
            std = torch.std(self.test_data[:, i])
            self.test_data[:, i] = (self.test_data[:, i] - mean) / std

    def _h(self, x, weights):
        return torch.matmul(x, weights)

    def _cost_function(self, x, y, weights):
        return ((self._h(x, weights) - y).T @ (self._h(x, weights) - y)) / (
            2 * y.shape[0]
        )

    def test(self):
        return self._cost_function(self.x, self.y, self.model["weights"])[0][0]