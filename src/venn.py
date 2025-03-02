import sys
from collections import deque, defaultdict
import random

from scheduler import Scheduler
from irs import IRS
from log import get_logger

scheduler_logger = get_logger('Scheduler')


class VennScheduler(Scheduler):
    def __init__(self, offer_size):
        # tri-partition the task based on workload/deadline and clients based on comm+comp
        Scheduler.__init__(self, offer_size )
        self.window_size = 100
        self.checkin_window = [deque([], maxlen=self.window_size ) for _ in range(5)]
        self.checkin_client = deque([], maxlen=self.window_size * 10 )
        self.adaptive_offer_size = offer_size
        self.job_demand = defaultdict(int)
        self.removed_job = set()
        self.job_group = defaultdict(list)
        self.init_allocation = {}
        self.traffic = {}
        self.job_avg_traffic = defaultdict(list)
        self.job_workload = {}
        self.buffer_size = {}
        self.job_last_req_time = {}
        self.job_deadline = {}
        self.job_end_time = defaultdict(list)
        self.job_request_count = defaultdict(list)

        self.remaining_round_per_eli = {}
        self.job_est_duration = {}
        self.job_est_size = {}
        self.job_total_round = {}
        self.job_remaining_round = {}
        self.job_init_size = {}
        self.job_score = {}
        self.job_eligibility = {} # 1,2,3
        self.job_order = [0]
        self.eligiblity_list = set()
        self.running_job = set() # jobs whose one round has been started

    def _schedule_plan(self):
        # trigger upon job punch and remove
        traffic_list = [ (e_id, self.window_size * 60 / (self.checkin_window[e_id][-1] - self.checkin_window[e_id][0]) ) for e_id in self.eligiblity_list]
        traffic_list.sort(key=lambda x: x[1])

        scheduler_logger.info("Job group: ", self.job_group)
        # initial allocation plan
        checkin_client = self.checkin_client
        for e_id, _ in traffic_list:
            init_clt = 1
            to_remove = []
            for clt in checkin_client:
                if e_id in clt :
                    init_clt += 1
                    to_remove.append(clt)
            for clt in to_remove:
                checkin_client.remove(clt)
            self.init_allocation[e_id] = init_clt
            for i, (job_id, job_size) in enumerate(self.job_group[e_id]):
                self.job_score[job_id] = (len(self.job_group[e_id]) - i ) / init_clt
                # self.job_score[job_id] = (len(self.job_group[e_id]) - i ) / init_clt / (self.job_init_size[job_id]*self.job_total_round[job_id])
        scheduler_logger.info("Initial allocation", self.init_allocation)
        scheduler_logger.info("Initial job score", self.job_score)
        self.job_order = sorted(self.job_score, key=self.job_score.get, reverse=True)
        scheduler_logger.info("Job order: ", self.job_order)

    def punch_job(self, job_id, job_dict):
        # TODO: decide scheduling order here
        self.job_total_round[job_id] = job_dict['total_round']
        self.job_remaining_round[job_id] = job_dict['total_round']
        self.job_eligibility[job_id] = job_dict['eligibility']
        self.job_deadline[job_id] = job_dict['deadline']
        self.job_workload[job_id] = job_dict['workload']
        self.job_init_size[job_id] = job_dict['amount']
        self.buffer_size[job_id] = job_dict['buffer_size']
        self.eligiblity_list.add(job_dict['eligibility'])

        self.job_group[job_dict['eligibility']].append((job_id, job_dict['amount'] * job_dict['total_round']))
        # sort within group
        self.job_group[job_dict['eligibility']].sort(key=lambda x: x[1])
        self._schedule_plan()

    def register_round_stats(self, job_id, end, time, success):
        if end is None and success is None:
            return
        # triggered upon close round
        # Record job round duration/size; round completion / model update; update job score
        if success:
            self.job_remaining_round[job_id] -= 1
            self.job_end_time[job_id].append(time)
            # self.job_est_duration[job_id] = (self.job_end_time[job_id][-1] - self.job_end_time[job_id][0]) / (len(self.job_end_time[job_id])-1)
            self.job_est_size[job_id] = sum(self.job_request_count[job_id]) / len(self.job_request_count[job_id])
            self.job_request_count[job_id].append(0)

        if end :
            scheduler_logger.info(f"Finish and remove job {job_id}")
            del self.job_demand[job_id]
            del self.job_score[job_id]
            del self.job_remaining_round[job_id]
            self.job_group[self.job_eligibility[job_id]].remove((job_id, self.job_total_round[job_id] * self.job_init_size[job_id]))
            # for job in self.job_group[self.job_eligibility[job_id]]:
            #     if job[0] == job_id:
            #         self.job_group[self.job_eligibility[job_id]].remove(job)
            #         break
            self.removed_job.add(job_id)
            self._schedule_plan()


    def register_ack(self, accept_task_list):
        if accept_task_list:
            for job_id in accept_task_list:
                if job_id in self.job_demand:
                    self.job_demand[job_id] -= 1
                    self.job_request_count[job_id][-1] += 1
                    # if self.job_demand[job_id] == 0:
                    #     self.running_job.remove(job_id)

    def register_job(self, job_id, request, time):

        # trigger once there is new request
        # Record and detect job request pattern

        # scheduler_logger.info(f"Traffic per min for each job {self.traffic}")
        if job_id not in self.job_end_time:
            # initialize score; unknown duration
            self.job_est_size[job_id] = self.job_init_size[job_id]
            self.job_est_duration[job_id] = self.job_deadline[job_id] if self.job_deadline[job_id] > 0 else 3 * self.job_init_size[job_id]
            # self.job_score[job_id] = self.job_total_round[job_id] * request.amount * self.traffic[job_id] * avg_duration
            self.job_end_time[job_id].append(time)
            self.job_request_count[job_id].append(0)

        # assert job_id not in self.removed_job
        if job_id not in self.removed_job:
            # decide whether to accept the request based on traffic
            self.traffic[job_id] = self._cal_client_traffic(job_id)
            self.job_avg_traffic[job_id].append(self.traffic[job_id])
            if self.job_deadline[job_id] > 0:
                request_rate_permin = self.job_init_size[job_id] / (self.job_deadline[job_id] // 60)
                if 0.5 * request_rate_permin > self.traffic[job_id]: # consider the minimum response rate
                    self._reject_request(job_id)
                    scheduler_logger.info(f"Reject the request from job {job_id} for {request.amount} resources. ")
                    return
                # distinguish between incr request and request for new round

            if request.amount <= 1:
                self.job_demand[job_id] += 1 # where to clean up the demand for apple and google
            else:
                self.job_demand[job_id] = request.amount
                self.job_last_req_time[job_id] = time

                # self.job_score[job_id] = self._cal_irs_score(job_id)
                # self.job_score[job_id] *= max(self.job_request_count[job_id][-1] / self.job_init_size[job_id], 1)
                # self._cal_job_order()

    def schedule_task(self, client):
        for e in client.eligibility:
            self.checkin_window[e].append(client.time)
        self.checkin_client.append(client.eligibility)

        task_list = []
        # TODO: task offer size = 1
        # for job_id in self.running_job:
        #     if self.job_demand[job_id] > 0 and self.job_eligibility[job_id] in client.eligibility:
        #         task_list.append(job_id)
        #         return task_list
        for job_id in self.job_order:
            if self.job_demand[job_id] > 0 and self.job_eligibility[job_id] in client.eligibility:
                task_list.append(job_id)
                # self.running_job.add(job_id)
                return task_list
        return task_list

    def _cal_job_order(self):
        sorted_job = sorted(self.job_score.items(), key=lambda x: x[1])
        # remove job with deadline & targeted number of devices
        order = []
        for x in sorted_job:
            if self.job_demand[x[0]] > 0:
                order.append(x[0])

        self.job_order = order

    def _cal_client_traffic(self, job_id):
        # number of checkin per min
        traffic = self.window_size * 60 / max(1, self.checkin_window[self.job_eligibility[job_id]][-1] - self.checkin_window[self.job_eligibility[job_id]][0])
        return traffic

    def _cal_job_scores(self):
        pass
        # for job_id in self.job_demand:
        #     self.job_score[job_id] = self._cal_irs_score(job_id)

    def _reject_request(self, job_id):
        # TODO: trigger when the deadline job is not prioritized
        self.job_demand[job_id] = 0
        self.job_end_time[job_id][0] += self.job_deadline[job_id]

    def _cal_avg_traffic(self, job_id):
        # avg traffic over a day.
        job_traffic = self.traffic[job_id] if job_id not in self.job_avg_traffic else sum(
            self.job_avg_traffic[job_id]) / len(self.job_avg_traffic[job_id])

        return job_traffic

    def _cal_irs_score(self, job_id):
        pass

class VennReqScheduler(VennScheduler):
    # Round-based scheduler w/o matching
    def __init__(self, offer_size):
        super().__init__(offer_size)
        self.irs = IRS()

    def punch_job(self, job_id, job_dict):
        self.job_total_round[job_id] = job_dict['total_round']
        self.job_remaining_round[job_id] = job_dict['total_round']
        self.job_eligibility[job_id] = job_dict['eligibility']
        self.job_deadline[job_id] = job_dict['deadline']
        self.job_workload[job_id] = job_dict['workload']
        self.job_init_size[job_id] = job_dict['amount']
        self.buffer_size[job_id] = job_dict['buffer_size']
        self.eligiblity_list.add(job_dict['eligibility'])


    def register_job(self, job_id, request, time):
        # trigger once there is new request
        # Record and detect job request pattern
        self.irs.add_request(job_id, request.amount, self.job_eligibility[job_id])
        _ = self.irs.schedule_first_request_per_group(self.checkin_client)

        if job_id not in self.job_end_time:
            # initialize score; unknown duration
            self.job_est_size[job_id] = self.job_init_size[job_id]
            self.job_est_duration[job_id] = self.job_deadline[job_id] if self.job_deadline[job_id] > 0 else 3 * self.job_init_size[job_id]
            # self.job_score[job_id] = self.job_total_round[job_id] * request.amount * self.traffic[job_id] * avg_duration
            self.job_end_time[job_id].append(time)
            self.job_request_count[job_id].append(0)

        if job_id not in self.removed_job:
            # decide whether to accept the request based on traffic
            self.traffic[job_id] = self._cal_client_traffic(job_id)
            self.job_avg_traffic[job_id].append(self.traffic[job_id])
            if self.job_deadline[job_id] > 0:
                request_rate_permin = self.job_init_size[job_id] / (self.job_deadline[job_id] // 60)
                if 0.5 * request_rate_permin > self.traffic[job_id]: # consider the minimum response rate
                    self._reject_request(job_id)
                    scheduler_logger.info(f"Reject the request from job {job_id} for {request.amount} resources. ")
                    return
                # distinguish between incr request and request for new round

            if request.amount <= 1:
                self.job_demand[job_id] += 1 # where to clean up the demand for apple and google
            else:
                self.job_demand[job_id] = request.amount
                self.job_last_req_time[job_id] = time


    def schedule_task(self, client):
        for e in client.eligibility:
            self.checkin_window[e].append(client.time)
        self.checkin_client.append(client.eligibility)
        potential_job_list = self.irs.schedule_task(client.eligibility)

        # job list in the same group
        if potential_job_list:
            job_id = potential_job_list[0]
            job_remaining_demand = self.job_demand[job_id]
            for id in potential_job_list:
                if 0 < self.job_demand[id] < job_remaining_demand:
                    job_id = id
                    job_remaining_demand = self.job_demand[id]
            return [job_id]
        return []

    def register_ack(self, accept_task_list):
        if accept_task_list:
            for job_id in accept_task_list:
                if job_id in self.job_demand:
                    self.job_demand[job_id] -= 1
                    self.job_request_count[job_id][-1] += 1
                    if self.job_demand[job_id] == 0:
                        self.irs.remove_request(job_id, self.job_eligibility[job_id])
                        _ = self.irs.schedule_first_request_per_group(self.checkin_client)

    def register_round_stats(self, job_id, end, time, success):
        # triggered upon close round
        # Record job round duration/size; round completion / model update; update job score

        self.irs.remove_request(job_id, self.job_eligibility[job_id])
        _ = self.irs.schedule_first_request_per_group(self.checkin_client)
        if success:
            # ensure the job is removed from irs
            self.job_remaining_round[job_id] -= 1
            self.job_end_time[job_id].append(time)
            # self.job_est_duration[job_id] = (self.job_end_time[job_id][-1] - self.job_end_time[job_id][0]) / (len(self.job_end_time[job_id])-1)
            self.job_est_size[job_id] = sum(self.job_request_count[job_id]) / len(self.job_request_count[job_id])
            self.job_request_count[job_id].append(0)
        if end:
            scheduler_logger.info(f"Finish and remove job {job_id}")
            del self.job_demand[job_id]
            del self.job_remaining_round[job_id]
            self.removed_job.add(job_id)


class VennMatchScheduler(VennReqScheduler):
    def __init__(self, offer_size):
        super().__init__(offer_size)
        self._init_tier_match()

    def _tier_match(self, comp, comm):
        for i, threshold in enumerate(self.tier_threshold_list):
            dur = comp * 60 + 10 / comm
            if dur < threshold:
                return self.num_tier - 1 - i # 0-based tier
        return 0

    def _init_tier_match(self):
        # TODO: automate the tier partition
        # tier_id : slow to fast
        # 57.90304761963098 - 25
        # 72.96072339398526
        # 119.97790315633219 - 50
        # 155.18489017730852
        # 170.63337232978574 - 75
        # 274.2717822683097

        if sys.argv[-1] == '3':
            self.tier_threshold_list = [72, 170]
            self.speed_up = [1, 170/274,72/274 ]
            self.response_time = 274 / 60
        elif sys.argv[-1] == '4':
            self.tier_threshold_list = [57, 120 , 170]
            self.speed_up = [1, 170/274, 120/274, 57/274 ]
            self.response_time = 274 / 60
        else:
            self.tier_threshold_list = [120]
            self.speed_up = [1, 120/274]
            self.response_time = 274 / 60

        # if sys.argv[-1] == '3':
        #     self.tier_threshold_list = [36, 77]
        #     self.speed_up = [1, 77/137,36/137 ]
        #     self.response_time = 140 / 60
        # elif sys.argv[-1] == '4':
        #     self.tier_threshold_list = [28, 60 , 85]
        #     self.speed_up = [1, 85/137, 60/137, 28/137 ]
        #     self.response_time = 150 / 60
        # else:
        #     self.tier_threshold_list = [60]
        #     self.speed_up = [1, 60/137]
        #     self.response_time = 150 / 60


        self.num_tier = len(self.tier_threshold_list) + 1
        self.job_tier = {}

    def register_job(self, job_id, request, time):

        self.irs.add_request(job_id, request.amount, self.job_eligibility[job_id])
        _ = self.irs.schedule_first_request_per_group(self.checkin_client)

        if job_id not in self.job_end_time:
            self.job_est_size[job_id] = self.job_init_size[job_id]
            # self.job_est_duration[job_id] = self.job_deadline[job_id] if self.job_deadline[job_id] > 0 else 3 * self.job_init_size[job_id]
            self.job_est_duration[job_id] = 3 * self.job_init_size[job_id]
            self.job_end_time[job_id].append(time)
            self.job_request_count[job_id].append(0)

        # assert job_id not in self.removed_job
        if job_id not in self.removed_job:
            # decide whether to accept the request based on traffic
            self.traffic[job_id] = self._cal_client_traffic(job_id)
            self.job_avg_traffic[job_id].append(self.traffic[job_id])
            if self.job_deadline[job_id] > 0:
                request_rate_permin = self.job_init_size[job_id] / ((self.job_deadline[job_id] - self.job_deadline[job_id]) //  60)
                print(f"Request rate per min: {request_rate_permin} v.s. traffic: {self.traffic[job_id]}")
                if  request_rate_permin > self.traffic[job_id]: # consider the minimum response rate
                    self._reject_request(job_id)
                    scheduler_logger.info(f"Reject the request from job {job_id} for {request.amount} resources. ")
                    return
                # distinguish between incr request and request for new round

            if request.amount <= 1:
                # Do not optimize for incremental request
                self.job_demand[job_id] += 1
            else:
                # if job_id in self.job_tier:
                #     del self.job_tier[job_id]
                self.job_demand[job_id] = request.amount
                self.job_last_req_time[job_id] = time

                # if this job is the first job in the group, then assign a tier to it
                first_pos = False
                # for gid in self.irs.job_group_list:
                group = self.irs.job_group_list[self.job_eligibility[job_id] + 1]
                if group.job_list[0][1] == job_id:
                    first_pos = True

                if first_pos and ( self.job_deadline[job_id] > 0 and self.num_tier * request.amount / self.traffic[job_id] + self.response_time < self.job_deadline[job_id] / 60 or self.job_deadline[job_id] == 0):
                    c_ratio = self.response_time / (request.amount / self.traffic[job_id] )
                    scheduler_logger.info(f"Current ratio: {c_ratio} for job {job_id} with {request.amount}/{self.traffic[job_id]} resources. ")
                    random_tier_id = random.randint(0, self.num_tier - 1)

                    if self.num_tier < (1 - self.speed_up[random_tier_id]) * c_ratio + 1 :
                        self.job_tier[job_id] = random_tier_id
                        scheduler_logger.info(f"Assign job {job_id} to tier {random_tier_id} with {request.amount} resources. ")


    def register_round_stats(self, job_id, end, time, success):
        # triggered upon close round
        # Record job round duration/size; round completion / model update; update job score

        self.irs.remove_request(job_id, self.job_eligibility[job_id])
        _ = self.irs.schedule_first_request_per_group(self.checkin_client)

        if success:
            self.job_remaining_round[job_id] -= 1
            self.job_end_time[job_id].append(time)
            self.job_est_size[job_id] = sum(self.job_request_count[job_id]) / len(self.job_request_count[job_id])
            self.job_request_count[job_id].append(0)

            if self.buffer_size[job_id] > 0:
                if job_id in self.job_order[:1]:
                    c_ratio = self.response_time / (self.job_init_size[job_id] / self._cal_client_traffic(job_id))
                    random_tier_id = random.randint(0, self.num_tier - 1)
                    if self.num_tier < (1 - self.speed_up[random_tier_id]) * c_ratio + 1:
                        self.job_tier[job_id] = random_tier_id

        if end :
            scheduler_logger.info(f"Finish and remove job {job_id}")
            del self.job_demand[job_id]
            del self.job_remaining_round[job_id]
            self.removed_job.add(job_id)

        if job_id in self.job_tier:
            del self.job_tier[job_id]

    def schedule_task(self, client):
        for e in client.eligibility:
            self.checkin_window[e].append(client.time)
        self.checkin_client.append(client.eligibility)

        device_tier = self._tier_match(client.computation, client.communication)
        potential_job_list = self.irs.schedule_task(client.eligibility)

        if potential_job_list:
            job_demand_list = [(jid, self.job_demand[jid]) for jid in potential_job_list]
            sorted_job_demand = sorted(job_demand_list, key=lambda x: x[1])
            for job_id, demand in sorted_job_demand:
                if demand > 0:
                    if (job_id in self.job_tier and self.job_tier[job_id] == device_tier) or job_id not in self.job_tier:
                        return [job_id]
        return []


class VennMatcher(VennMatchScheduler):
    def __init__(self, offer_size):
        super().__init__(offer_size)
        self.job_response_time = defaultdict(list)
        self.job_order = []


    def punch_job(self, job_id, job_dict):
        self.job_eligibility[job_id] = job_dict['eligibility']
        self.buffer_size[job_id] = job_dict['buffer_size']
        self.job_deadline[job_id] = job_dict['deadline']
        self.job_order.append(job_id)

    def register_round_stats(self, job_id, end, time, success):
        if success:
            pass
        if end:
            # scheduler_logger.info(f"Finish and remove job {job_id}")
            del self.job_demand[job_id]
            self.removed_job.add(job_id)
            self.job_order.remove(job_id)

    def register_job(self, job_id, request, time):
        if job_id not in self.removed_job:
            # decide whether to accept the request based on traffic
            self.traffic[job_id] = self._cal_client_traffic(job_id)
            self.job_avg_traffic[job_id].append(self.traffic[job_id])
            if self.job_deadline[job_id] > 0:
                request_rate_permin = self.job_init_size[job_id] / (self.job_deadline[job_id] // 60)
                if 0.75 * request_rate_permin > self.traffic[job_id]:  # consider the minimum response rate
                    self._reject_request(job_id)
                    scheduler_logger.info(f"Reject the request from job {job_id} for {request.amount} resources. ")
                    return


            if request.amount == 1:
                self.job_demand[job_id] += 1  # where to clean up the demand for apple and google
            else:
                self.job_demand[job_id] = request.amount
                if job_id in self.job_tier:
                    del self.job_tier[job_id]

                # whether the job is the first job with positive demand
                first_pos = False
                for job in self.job_order:
                    if self.job_demand[job] > 0 and not first_pos:
                        if job == job_id:
                            first_pos = True

                if first_pos:
                # if job_id in self.job_order[:1] and self.job_deadline[job_id] == 0:
                    self.traffic[job_id] = self._cal_client_traffic(job_id)
                    random_tier_id = random.randint(0, self.num_tier - 1)
                    c_ratio = self.response_time / (request.amount / self.traffic[job_id] )

                    if self.num_tier < (1 - self.speed_up[random_tier_id]) * c_ratio + 1 :
                        self.job_tier[job_id] = random_tier_id
                        scheduler_logger.info(f"Assign job {job_id} to tier {random_tier_id} with {request.amount} resources. ")


    def register_ack(self, accept_task_list):
        if accept_task_list:
            for job_id in accept_task_list:
                # self.job_response_time[job_id].append(duration)
                if job_id in self.job_demand:
                    self.job_demand[job_id] -= 1


    def schedule_task(self, client):
        for e in client.eligibility:
            self.checkin_window[e].append(client.time)
        self.checkin_client.append(client.eligibility)

        task_list = []
        # IRS heuristic
        for job_id in self.job_demand:
            if self.job_demand[job_id] > 0 and self.job_eligibility[job_id] in client.eligibility:
                if job_id in self.job_tier:
                    if self.job_tier[job_id] == self._tier_match(client.computation, client.communication):
                        task_list.append(job_id)
                else:
                    task_list.append(job_id)
        # random.shuffle(task_list)
        return task_list

class VennFairness(VennMatchScheduler):
    def __init__(self, offer_size):
        super().__init__(offer_size)
        self.fairness_knob = float(sys.argv[-1])

    def init_tier_match(self):
        self.tier_threshold_list = [120]
        self.speed_up = [1, 120/274]
        self.response_time = 274 / 60
        self.num_tier = len(self.tier_threshold_list) + 1
        self.job_tier = {}



    def register_round_stats(self, job_id, end, time, success):
        # triggered upon close round
        # Record job round duration/size; round completion / model update; update job score
        if success:
            self.job_remaining_round[job_id] -= 1
            self.job_end_time[job_id].append(time)
            self.job_est_size[job_id] = sum(self.job_request_count[job_id]) / len(self.job_request_count[job_id])
            self.job_request_count[job_id].append(0)


        if end :
            scheduler_logger.info(f"Finish and remove job {job_id}")
            del self.job_demand[job_id]
            del self.job_score[job_id]
            del self.job_remaining_round[job_id]
            self.job_group[self.job_eligibility[job_id]].remove((job_id, self.job_total_round[job_id] * self.job_init_size[job_id]))
            self.removed_job.add(job_id)
            self._schedule_plan()

        if success and not end:
            job_score = self.job_score
            for job in self.job_demand:
                time_usage = (self.job_end_time[job_id][-1] - self.job_end_time[job][0]) / 60
                time_fair = len(self.job_end_time) * (  self.job_total_round[job] * self.job_init_size[job]) / self._cal_avg_traffic(job)
                time_fair += self.job_total_round[job] * 300
                # TODO: save recomputation
                job_score[job_id] *= pow(time_usage / time_fair, self.fairness_knob)
                # scheduler_logger.info(f'Fare JCT of job {job}: {time_fair}')
            # time_usage = ( self.job_end_time[job_id][-1] - self.job_end_time[job_id][0] ) / 60
            # time_fair = len(self.job_end_time) * (self.job_total_round[job_id] * self.job_init_size[job_id]) / self._cal_avg_traffic(job_id)
            #
            # job_score[job_id] *= pow( time_usage/time_fair, self.fairness_knob)
            self.job_order = sorted(job_score, key=job_score.get, reverse=True)

            if self.buffer_size[job_id] > 0:
                if job_id in self.job_tier:
                    del self.job_tier[job_id]
                if job_id in self.job_order[:1]:
                    c_ratio = self.response_time / (self.job_init_size[job_id] / self._cal_client_traffic(job_id))
                    random_tier_id = random.randint(0, self.num_tier - 1)
                    if self.num_tier < (1 - self.speed_up[random_tier_id]) * c_ratio + 1:
                        self.job_tier[job_id] = random_tier_id
