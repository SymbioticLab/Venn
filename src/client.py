
import random


class Client():
    def __init__(self, id, time, end, computation, communication, eligibility, task_capacity = 1):
        # assume check in once
        self.id = id
        self.time = time
        self.end =end
        # print(self.end - self.time)
        self.computation = computation
        self.communication = communication
        self.eligibility = eligibility # [1,2,...]
        self.cur_task = []
        self.task_capacity = task_capacity

    def assign(self, time, task_offer, workload, comm ):
        # return None if reject
        if len(self.cur_task) == 0:
            # if time + comm[0] / self.communication > self.end:
            #     return None
            self.cur_task.append(task_offer[0])
            return self.cur_task
        else:
            print(f'Client {self.id} is busy with task {self.cur_task}')
            return None

    def execute(self, time, workload, comm):
        duration = workload * self.computation + comm / self.communication * 2
        # self.cur_task.pop(0)
        if time + duration > self.end: # go offline
            return -1
        return time + duration

class GoogleClient(Client):

    def __init__(self, id, time, end, computation, communication, eligibility, task_capacity = 1):
        # maintain a simple worker queue for determining which
        # training session to run next (we avoid running training
        # sessions on-device in parallel because of their high resource
        # consumption).
        Client.__init__(self, id, time, end, computation, communication, eligibility, task_capacity = 1)
        self.available_time = self.time
        self.task_order = -1

    def assign(self, time, task_offer, workload, comm):
        # input task_offer size = 1
        if self.available_time < self.end:
            self.cur_task += task_offer
            self.task_order += 1
            return [self.cur_task[self.task_order]]
            # return [self.cur_task.pop(0)]
        else:
            return None

    def execute(self, time, workload, comm):
        duration = workload * self.computation + comm / self.communication * 2
        time = max(self.available_time, time)
        if time + duration > self.end:
            if self.available_time <= self.time:
                # never success
                self.available_time = self.end
                return -1
            else:
                # print(f'Client {self.id} is busy with previous task ')
                self.available_time = self.end
                return -2
        self.available_time = time + duration
        return self.available_time

class AgnosticClient(Client):
    # assume the device cannot predict the execution time, but only look at the average workload
    def assign(self, time, task_offer, workload, comm ):
        # assume only choose one feasible task at random
        if len(self.cur_task) == 0:
            for i, task in enumerate(task_offer):
                # duration = workload[i] * self.computation + comm[i] / self.communication * 2
                duration = workload[i] + comm[i] * 2
                if time + duration <= self.end:
                    self.cur_task.append(task)
                    time += duration
            task_list = random.sample(self.cur_task, min(len(self.cur_task), self.task_capacity))
            return task_list
        else:
            print(f'Client {self.id} is busy with task {self.cur_task}')
            return None

class FIFOClient(Client):
    # pick tasks based on assigned task order; apple's client; cannot predict execution time
    def assign(self, time, task_offer, workload, comm):
        # assume only choose one task
        if len(self.cur_task) == 0:
            for i, task in enumerate(task_offer):
                duration = workload[i] + comm[i] * 2
                # duration = workload[i] * self.computation + comm[i] / self.communication * 2
                if time + duration <= self.end:
                    self.cur_task.append(task)
                    time += duration
            task_list = self.cur_task[:min(len(self.cur_task), self.task_capacity)]
            return task_list
        else:
            print(f'Client {self.id} is busy with task {self.cur_task}')
            return None

class MultiFIFOClient(FIFOClient):
    def __init__(self, id, time, end, computation, communication, eligibility ):
        FIFOClient.__init__(self, id, time, end, computation, communication, eligibility, task_capacity = 3)

class OfferClient(FIFOClient):
    # fifo order to execute k tasks in task offer; aware of online duration
    def __init__(self, id, time, end, computation, communication, eligibility):
        FIFOClient.__init__(self, id, time, end, computation, communication, eligibility, task_capacity=3)

    def assign(self, time, task_offer, workload, comm):

        for i, task in enumerate(task_offer):
            duration = workload[i] * self.computation + comm[i] / self.communication * 2
            if time + duration <= self.end:
                self.cur_task.append(task)
                time += duration

        if len(self.cur_task) ==0 :
            return None

        return self.cur_task[:min(len(self.cur_task), self.task_capacity)]

