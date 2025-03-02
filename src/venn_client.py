from client import Client


class VennClient(Client):
    # TODO: should check the time of the task
    # assume the device cannot predict the execution time, but only look at the average workload
    # Pick one task in the fifo order
    def assign(self, time, task_offer, workload, comm):
        # assume only choose one task
        if len(self.cur_task) == 0:
            for i, task in enumerate(task_offer):
                duration = workload[i] + comm[i] * 2
                if time + duration <= self.end:
                    self.cur_task.append(task)
                    time += duration
            task_list = self.cur_task[:min(len(self.cur_task), 1)]
            return task_list
        else:
            print(f'Client {self.id} is busy with task {self.cur_task}')
            return None

class VennSpecialClient(Client):
    # assume the device cannot predict the execution time, but only look at the average workload
    # Pick one task in the fifo order
    def assign(self, time, task_offer, workload, comm):
        # assume only choose one task
        if len(self.cur_task) == 0:
            for i, task in enumerate(task_offer):
                duration = workload[i] * self.computation + comm[i]  / self.communication * 2
                # duration = workload[i] + comm[i] * 2
                if time + duration <= self.end:
                    self.cur_task.append(task)
                    time += duration
            task_list = self.cur_task[:min(len(self.cur_task), 1)]
            return task_list
        else:
            print(f'Client {self.id} is busy with task {self.cur_task}')
            return None