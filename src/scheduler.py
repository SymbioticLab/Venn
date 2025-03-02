import random
from collections import deque
# from config import *
google_job = ['Job', 'AgnosticJob', 'GoogleJob', 'DecentralizedJob']
apple_job = ['AppleJob', 'DecAppleJob']

class Scheduler():

    # no knowledge over private device eligibility
    def __init__(self, offer_size = 1):
        self.job_demand = {}
        self.offer_size = offer_size
        # self.job_request = {}
        self.sort_id = []
        self.job_eligibility = {}

    def punch_job(self, job_id, job_dict):
        self.job_eligibility[job_id] = job_dict['eligibility']

    def register_job(self, job_id, request, job_type): # upon new request submitted
        self.job_demand[job_id] = request.amount

    def schedule_task(self, client):
        task_list = []
        # check eligibility
        for job_id in self.job_demand :
            if self.job_demand[job_id] > 0 and \
                    self.job_eligibility[job_id] in client.eligibility:
                task_list.append(job_id)

        if len(task_list) == 0:
            return None

        task_list = random.sample(task_list, min(len(task_list), self.offer_size))
        for task_id in task_list:
            self.job_demand[task_id] -= 1

        return task_list

    def register_ack(self, accept_task_list):
        pass

    def register_round_stats(self, job_id, round_stats, time, success):
        pass

    def clear_demand(self, job_id):
        self.job_demand[job_id] = 0

class MetaScheduler(Scheduler):
    def __init__(self, offer_size=1):
        Scheduler.__init__(self, 1 )

class CentralScheduler(Scheduler):
    # Meta w/ knowledge; fully centralized & full knowledge (without offer delay)
    def __init__(self, offer_size=1):
        Scheduler.__init__(self, 1 )
        self.job_workload = {}
        self.job_comm = {}

    def register_job(self, job_id, request, time):
        self.job_demand[job_id] = request.amount
        self.job_workload[job_id] = request.workload
        self.job_comm[job_id] = request.comm
        # self.job_request = request

    def schedule_task(self, client):
        task_list = []
        # check eligibility
        for job_id in self.job_demand :
            if self.job_demand[job_id] > 0 and \
                    self.job_eligibility[job_id] in client.eligibility:
                duration = self.job_workload[job_id] * client.computation + self.job_comm[job_id] / client.communication*2
                if client.time + duration <= client.end :
                    task_list.append(job_id)

        if len(task_list) == 0:
            return None

        task_list = random.sample(task_list, min(len(task_list), self.offer_size))
        for task_id in task_list:
            self.job_demand[task_id] -= 1

        return task_list

class PapayaScheduler(Scheduler):
    def __init__(self, offer_size):
        Scheduler.__init__(self, 1 )

    # handle Async request assume no full knowledge
    def register_job(self, job_id, request, time):
        if job_id in self.job_demand:
            self.job_demand[job_id] += request.amount
        else:
            self.job_demand[job_id] = request.amount

    def register_round_stats(self, job_id, end, time, success):
        # give out offer util the job finish at all
        if end:
            # print(f"Finish and remove job {job_id}")
            del self.job_demand[job_id]

class AppleScheduler(Scheduler):
    def schedule_task(self, client):
        task_list = []
        # check eligibility
        for job_id in self.job_demand:
            if self.job_demand[job_id] > 0 and \
                    self.job_eligibility[job_id] in client.eligibility:  # [1:-1].split(', '):
                task_list.append(job_id)

        if len(task_list) == 0:
            return None
        task_list = random.sample(task_list, min(len(task_list), self.offer_size))
        # TODO: should pretend to download all task (apple)? or still filtered by eligibility
        return task_list

    def register_round_stats(self, job_id, task_stats, time, success):
        # give out offer util the job finish at all
        if task_stats:
            # print(f"Finish and remove job {job_id}")
            del self.job_demand[job_id]

class AppleGJobScheduler(AppleScheduler):
    # count demand on selection window
    def register_ack(self, accept_task_list):
        if accept_task_list:
            for task in accept_task_list:
                if task in self.job_demand:
                    self.job_demand[task] -= 1

class ApplePJobScheduler(AppleScheduler):

    def __init__(self, offer_size):
        AppleScheduler.__init__(self, offer_size)
        self.removed_job = []


    def register_job(self, job_id, request, time):
        if job_id in self.job_demand:
            self.job_demand[job_id] += request.amount
        elif job_id not in self.removed_job:
            self.job_demand[job_id] = request.amount

    def register_round_stats(self, job_id, task_stats, time, success):
        # give out offer util the job finish at all
        if task_stats:
            # print(f"Finish and remove job {job_id}")
            del self.job_demand[job_id]
            self.removed_job.append(job_id)

    # def register_ack(self, accept_task_list):
    #     if accept_task_list:
    #         for task in accept_task_list:
    #             if task in self.job_demand:
    #                 self.job_demand[task] -= 1
    # register_ack cannot ensure the task would be finished by clients eventually.

class TaskOfferScheduler(AppleScheduler):
    # TODO: when to announce more resources if failure
    pass

class FIFOScheduler(AppleScheduler):
    def schedule_task(self, client):
        task_list = []
        # check eligibility
        for job_id in self.job_demand:
            if self.job_demand[job_id] > 0 and \
                    self.job_eligibility[job_id] in client.eligibility:
                task_list.append(job_id)

        if len(task_list) == 0:
            return None
        task_list = task_list[:min(len(task_list), self.offer_size)]
        return task_list

class FIFOPJobScheduler(FIFOScheduler, ApplePJobScheduler):
    pass

class FIFOGJobScheduler(FIFOScheduler, AppleGJobScheduler):
    pass

class AmountScheduler(AppleScheduler):
    def __init__(self, offer_size):
        AppleScheduler.__init__(self, offer_size )
        self.job_min_amount = {}

    def register_job(self, job_id, request, time):

        self.job_demand[job_id] = request.amount
        self.job_min_amount[job_id] = request.amount * request.fraction
        self.sort_id = self._sort_amount()

    def _sort_amount(self):
        sorted_amount = sorted(self.job_min_amount.items(), key=lambda x: x[1])
        sort_id = [x[0] for x in sorted_amount]
        return sort_id

    def schedule_task(self, client):
        task_list = []
        # check eligibility
        for job_id in self.job_demand:
            if self.job_demand[job_id] > 0 and \
                    self.job_eligibility[job_id] in client.eligibility:
                task_list.append(job_id)

        if len(task_list) == 0:
            return None
        # sort by min_part
        # sort_id = self._sort_amount()
        new_list = []
        for task_id in self.sort_id:
            if task_id in task_list:
                new_list.append(task_id)
        task_list = new_list[:min(len(new_list), self.offer_size)]
        return task_list

class AmountGJobScheduler(AmountScheduler, AppleGJobScheduler):
    pass

class WorkloadScheduler(AppleScheduler):
    def __init__(self, offer_size):
        AppleScheduler.__init__(self, offer_size )
        self.job_workload = {}

    def register_job(self, job_id, request, time):
        self.job_demand[job_id] = request.amount
        self.job_workload[job_id] = request.workload
        self.sort_id = self._sort_wl()

    def _sort_wl(self):
        sorted_wl = sorted(self.job_workload.items(), key=lambda x: x[1], reverse = True)
        sort_id = [x[0] for x in sorted_wl]
        return sort_id

    def schedule_task(self, client):
        task_list = []
        # check eligibility
        for job_id in self.job_demand:
            if self.job_demand[job_id] > 0 and \
                    self.job_eligibility[job_id]in client.eligibility:
                task_list.append(job_id)

        if len(task_list) == 0:
            return None
        # sort by min_part
        # sort_id = self._sort_wl()
        new_list = []
        for task_id in self.sort_id:
            if task_id in task_list:
                new_list.append(task_id)
        task_list = new_list[:min(len(new_list), self.offer_size)]
        return task_list

class DeadlineScheduler(AppleScheduler):
    def __init__(self, offer_size):
        AppleScheduler.__init__(self, offer_size )
        self.job_ddl = {}

    def register_job(self, job_id, request, job_type):
        self.job_demand[job_id] = request.amount
        self.job_ddl[job_id] =  request.duration
        self.sort_id = self._sort_ddl()

    def _sort_ddl(self):
        # TODO: the sorting order
        sorted_ddl = sorted(self.job_ddl.items(), key=lambda x: x[1], reverse= False )
        sort_id = [x[0] for x in sorted_ddl]
        return sort_id

    def schedule_task(self, client):
        task_list = []
        # check eligibility
        for job_id in self.job_demand:
            if self.job_demand[job_id] > 0 and \
                    self.job_eligibility[job_id] in client.eligibility:
                task_list.append(job_id)

        if len(task_list) == 0:
            return None
        # sort by min_part
        # sort_id = self._sort_ddl()
        new_list = []
        for task_id in self.sort_id:
            if task_id in task_list:
                new_list.append(task_id)
        task_list = new_list[:min(len(new_list), self.offer_size)]
        return task_list

class UrgencyScheduler(DeadlineScheduler):
    def register_job(self, job_id, request):
        self.job_demand[job_id] = request.amount
        self.job_ddl[job_id] = (request.workload+request.comm*2) / request.duration
        self.sort_id = self._sort_ddl()

    def _sort_ddl(self):
        sorted_ddl = sorted(self.job_ddl.items(), key=lambda x: x[1], reverse= True )
        sort_id = [x[0] for x in sorted_ddl]
        return sort_id


class FailureScheduler(AppleScheduler):
    # TODO: initialize a different job that give success_round_rate
    def __init__(self, offer_size):
        AppleScheduler.__init__(self, offer_size )
        self.job_succ_round_rate = {}

    def register_round_stats(self, job_id, success_round_rate, time, success):
        self.job_succ_round_rate[job_id] = success_round_rate
        self.sort_id = self._sort_success()

    def _sort_success(self):
        sorted_succ = sorted(self.job_succ_round_rate.items(), key=lambda x: x[1], reverse = False  )
        sort_id = [x[0] for x in sorted_succ]
        return sort_id

    def schedule_task(self, client):
        task_list = []
        # check eligibility
        for job_id in self.job_demand:
            if self.job_demand[job_id] > 0 and \
                    self.job_eligibility[job_id] in client.eligibility:
                task_list.append(job_id)

        if len(task_list) == 0:
            return None

        new_list = []
        for task_id in self.sort_id:
            if task_id in task_list:
                new_list.append(task_id)
        task_list = new_list[:min(len(new_list), self.offer_size)]
        return task_list

class FreqScheduler(AmountScheduler):
    def __init__(self, offer_size):
        AmountScheduler.__init__(self, offer_size )

    def register_job(self, job_id, request):
        self.job_demand[job_id] =request.amount

        self.job_min_amount[job_id] = request.amount / request.duration
        self.sort_id = self._sort_amount()

class HeterScheduler(AppleScheduler):
    def __init__(self, offer_size):
        # tri-partition the task based on workload/deadline and clients based on comm+comp
        AppleScheduler.__init__(self, offer_size )
        self.job_urgency = {}

    def register_job(self, job_id, request, job_type):
        self.job_demand[job_id] = request.amount
        self.job_urgency[job_id] = (request.workload+request.comm*2) / request.duration
        self.sort_id = self._sort_urgency()

    def _sort_urgency(self):
        sorted_urg = sorted(self.job_urgency.items(), key=lambda x: x[1], reverse = False)
        sort_id = [x[0] for x in sorted_urg]
        classifies_id = [  sort_id[:len(sort_id)//3],
                           sort_id[len(sort_id) // 3:len(sort_id) * 2 // 3],
                           sort_id[len(sort_id) * 2 // 3:] ]

        return classifies_id

    def _classify_client(self, client):
        avg_comp = 78
        avg_comm = 13736
        # customized sorted task id
        if client.communication > avg_comm and client.computation < avg_comp: # poor
            task_order = self.sort_id[0] + self.sort_id[1] + self.sort_id[2]
        elif client.communication < avg_comm and client.computation > avg_comp: # good
            task_order = self.sort_id[2] + self.sort_id[1] + self.sort_id[0]
        else:
            task_order = self.sort_id[1] + self.sort_id[2] + self.sort_id[0]

        return task_order


    def schedule_task(self, client):
        task_list = []
        # check eligibility
        for job_id in self.job_demand:
            if self.job_demand[job_id] > 0 and \
                    self.job_eligibility[job_id] in client.eligibility:
                task_list.append(job_id)

        if len(task_list) == 0:
            return None

        # sort by min_part
        task_order = self._classify_client(client)

        new_list = []
        for task_id in task_order:
            if task_id in task_list:
                new_list.append(task_id)
        task_list = new_list[:min(len(new_list), self.offer_size)]
        return task_list

class TrafficScheduler(AmountScheduler):
    # TODO: only for Google/Apple
    # Shrink offer size based on real-time traffic to reduce waste; amount-prioritized order
    def __init__(self, offer_size):
        # tri-partition the task based on workload/deadline and clients based on comm+comp
        AmountScheduler.__init__(self, offer_size )
        self.window_size = 50
        self.checkin_window = deque([], maxlen=self.window_size )
        self.adaptive_offer_size = offer_size
        self.traffic = 1
        self.total_demand = 0
        self.positive_demand = 0
        self.initial_overcommit = 1.3
        self.job_demand_per_min = {}
        self.job_type_dict = {}

    def register_round_stats(self, job_id, round_stats, time, success):
        if round_stats:
            del self.job_demand[job_id]

    def register_ack(self, accept_task_list):
        if accept_task_list:
            for task_id in accept_task_list:
                if task_id in self.job_demand:
                    if self.job_type_dict[task_id] in google_job:
                        self.job_demand[task_id] -= 1
                    # TODO: refill the job demand
                    elif self.job_type_dict[task_id] in apple_job:
                        self.job_demand[task_id] -= 1/self.initial_overcommit

    def register_job(self, job_id, request, job_type):
        # register at the beginning of each request
        self.job_type_dict[job_id] = job_type
        self.job_demand[job_id] = request.amount
        self.job_min_amount[job_id] = request.amount # * request.fraction
        # self.sort_id = self._sort_amount()
        self.sort_id = sorted(job_id for job_id in self.job_demand if self.job_demand[job_id] > 0 )
        self.traffic = self._cal_client_traffic()
        # TODO: job_demand_per_min only works for google's job; different calculation for apple's job
        offer_lower_limit = 1
        if job_type in google_job:
            self.job_demand_per_min[job_id] = request.amount / (request.duration / 60)
        elif job_type in apple_job:
            # offer_lower_limit = 0
            apple_round_duration =  request.amount * self.initial_overcommit / self.traffic + request.workload / 60 * 1.5
            self.job_demand_per_min[job_id] = request.amount / apple_round_duration

        self.total_demand = sum(self.job_demand_per_min[job_id] for job_id in self.job_demand if self.job_demand[job_id] > 0 )
        print(f"current traffic per min {self.traffic} v.s. total demand {self.total_demand}")
        # TODO: tune the upper limit for offer size
        # reuse the clients when the contention is large
        self.positive_demand = sum([self.job_demand[job] > 0 for job in self.job_demand])

        self.adaptive_offer_size = max(offer_lower_limit, int(min( self.total_demand/self.traffic , 1) * self.positive_demand))
        # self.adaptive_offer_size = round(self.traffic / self.total_demand+0.5)
        print(f"current offer size {self.adaptive_offer_size}/{self.positive_demand}")

    def _cal_client_traffic(self):
        # number of checkin per min
        traffic = self.window_size * 60 / (self.checkin_window[-1] - self.checkin_window[0])
        return traffic

    # def _check_unfinished_job(self):
    #     online_job = sum( [self.job_demand[job_id] > 0 for job_id in self.job_demand])
    #     if online_job == 0 and len(self.job_demand) > 0:
    #         pass # refill


    def schedule_task(self, client):
        self.checkin_window.append(client.time)
        task_list = []

        contention = self.total_demand / self.traffic
        if contention < 1 and random.random() > contention:
            return None

        # check eligibility
        for job_id in self.job_demand:
            if self.job_demand[job_id] > 0 and \
                    self.job_eligibility[job_id] in client.eligibility:
                task_list.append(job_id)

        if len(task_list) == 0:
            return None

        new_list = []
        for task_id in self.sort_id:
            if task_id in task_list:
                new_list.append(task_id)
        task_list = new_list[:min(len(new_list), self.adaptive_offer_size)]
        # print(f"Task offer: {task_list}")
        return task_list


class MixScheduler(AmountScheduler):
    def __init__(self, offer_size):
        AmountScheduler.__init__(self, offer_size )

    def register_job(self, job_id, request, job_type):
        self.job_demand[job_id] = request.amount
        # amount, workload, deadline
        normalized = [100, 45, 475 ]
        weight = [0.5, 0.5, 0.1, 0.1]
        
        self.job_min_amount[job_id] = weight[0] * request.amount / normalized[0] / (request.duration / normalized[2]) + \
                                     weight[1] * request.amount * request.fraction / normalized[0]

        self.sort_id = self._sort_amount()
