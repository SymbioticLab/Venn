from venn import VennScheduler 
import random


class FIFOScheduler(VennScheduler):
    def punch_job(self, job_id, job_dict):
        self.job_eligibility[job_id] = job_dict['eligibility']
        self.job_order.append(job_id)

    def register_round_stats(self, job_id, end, time, success):
        if end:
            # print(f"Finish and remove job {job_id}")
            del self.job_demand[job_id]
            self.job_order.remove(job_id)
            self.removed_job.add(job_id)

    def register_job(self, job_id, request, time):
        if job_id not in self.removed_job:
        # assert job_id not in self.removed_job
            if request.amount == 1:
                self.job_demand[job_id] += 1
            else:
                self.job_demand[job_id] = request.amount

    def register_ack(self, accept_task_list):
        if accept_task_list:
            for job_id in accept_task_list:
                if job_id in self.job_demand:
                    self.job_demand[job_id] -= 1

    def schedule_task(self, client):
        # task_list = []
        for job_id in self.job_order:
            if self.job_demand[job_id] > 0 and self.job_eligibility[job_id] in client.eligibility:
                return [job_id]

class FIFOReqScheduler(FIFOScheduler):
    # FIFO according to request arrival time
    def punch_job(self, job_id, job_dict):
        self.job_eligibility[job_id] = job_dict['eligibility']

    def register_round_stats(self, job_id, end, time, success):
        if end:
            # print(f"Finish and remove job {job_id}")
            del self.job_demand[job_id]
            self.removed_job.add(job_id)
        if job_id in self.job_order:
            self.job_order.remove(job_id)

    def register_job(self, job_id, request, time):
        if job_id not in self.removed_job:
        # assert job_id not in self.removed_job
            if request.amount == 1:
                self.job_demand[job_id] += 1
            else:
                self.job_demand[job_id] = request.amount
            self.job_order.append(job_id)

class RandomScheduler(FIFOScheduler):
    def schedule_task(self, client):
        task_list = []
        for job_id in self.job_demand:
            if self.job_demand[job_id] > 0 and self.job_eligibility[job_id] in client.eligibility:
                task_list.append(job_id)
        random.shuffle(task_list)
        return task_list

class SmallestScheduler(VennScheduler):
    # shortest remaining job first
    def punch_job(self, job_id, job_dict):
        self.job_total_round[job_id] = job_dict['total_round']
        self.job_eligibility[job_id] = job_dict['eligibility']
        self.job_init_size[job_id] = job_dict['amount']

    # smallest first
    def _cal_irs_score(self, job_id): #
        return self.job_total_round[job_id] * self.job_init_size[job_id]

    def register_round_stats(self, job_id, end, time, success):
        # Record job round duration/size; round completion / model update; update job score
        if success:
            # confirmed: should update the rounds; changing order is bad
            self.job_total_round[job_id] -= 1
            # self.job_end_time[job_id].append(time)
        if end:
            print(f"[{time}s] Finish and remove job {job_id}")
            del self.job_demand[job_id]
            self.removed_job.add(job_id)
            del self.job_score[job_id]

    def register_job(self, job_id, request, time):
        # Record and detect job request pattern
        if job_id not in self.job_demand:
            self.job_score[job_id] = self._cal_irs_score(job_id)

        # assert job_id not in self.removed_job
        if job_id not in self.removed_job:
            if request.amount == 1:
                self.job_demand[job_id] += 1 # where to clean up the demand for apple and google
            else:
                self.job_demand[job_id] = request.amount
                self._cal_job_scores()
                self._cal_job_order()
                # print(f"Scheduling order {self.job_order}")

    def _cal_job_scores(self):
        for job_id in self.job_demand:
            self.job_score[job_id] = self._cal_irs_score(job_id)

    def schedule_task(self, client):
        task_list = []
        for job_id in self.job_order:
            if self.job_demand[job_id] > 0 and self.job_eligibility[job_id] in client.eligibility:
               task_list.append(job_id)
        return task_list

    def register_ack(self, accept_task_list):
        if accept_task_list:
            for job_id in accept_task_list:
                if job_id in self.job_demand:
                    self.job_demand[job_id] -= 1

class SmallReqScheduler(SmallestScheduler):
    # smallest first
    def _cal_irs_score(self, job_id): #
        return self.job_demand[job_id]



class LASScheduler(FIFOScheduler):
    # Schedule based on number of devices acquired
    # allow one task in the offer
    def _schedule_plan(self):
        self.job_order = sorted(self.job_score, key=self.job_score.get, reverse=False)
        print("Job order: ", self.job_order)

    def punch_job(self, job_id, job_dict):
        self.job_score[job_id] = 0
        self.job_eligibility[job_id] = job_dict['eligibility']

    def register_job(self, job_id, request, time):
        if job_id not in self.removed_job:
            if request.amount == 1:
                self.job_demand[job_id] += 1
            else:
                self.job_demand[job_id] = request.amount
            self.job_score[job_id] += request.amount

    def register_round_stats(self, job_id, end, time, success):
        if end:
            # print(f"Finish and remove job {job_id}")
            del self.job_demand[job_id]
            self.job_order.remove(job_id)
            self.removed_job.add(job_id)
        if success:
            self._schedule_plan()

    def schedule_task(self, client):
        task_list = []
        for job_id in self.running_job:
            if self.job_demand[job_id] > 0 and self.job_eligibility[job_id] in client.eligibility:
                task_list.append(job_id)
                return task_list
        for job_id in self.job_order:
            if self.job_demand[job_id] > 0 and self.job_eligibility[job_id] in client.eligibility:
                task_list.append(job_id)
                self.running_job.add(job_id)
                return task_list
        return task_list

    def register_ack(self, accept_task_list):
        if accept_task_list:
            for job_id in accept_task_list:
                if job_id in self.job_demand:
                    self.job_demand[job_id] -= 1
                    if self.job_demand[job_id] == 0 and job_id in self.running_job:
                        self.running_job.remove(job_id)


class RandomOrderScheduler(LASScheduler):
    # Schedule based on number of rounds request
    # not applicable for async job
    def register_job(self, job_id, request, time):
        if job_id not in self.removed_job:
            if request.amount == 1:
                self.job_demand[job_id] += 1
            else:
                self.job_demand[job_id] = request.amount
            self.job_score[job_id] = random.random()
            self._schedule_plan()

    def _schedule_plan(self):
        self.job_order = sorted(self.job_score, key=self.job_score.get, reverse=False)
        print("Job order: ", self.job_order)


class ChoosyScheduler(VennScheduler):
    def __init__(self, offer_size):
        VennScheduler.__init__(self, offer_size)
        self.choosy_counter = {}


    def punch_job(self, job_id, job_dict):
        self.choosy_counter[job_id] = 0

        self.job_eligibility[job_id] = job_dict['eligibility']


    def register_round_stats(self, job_id, end, time, success):
        if end:
            # print(f"Finish and remove job {job_id}")
            del self.job_demand[job_id]
            self.removed_job.add(job_id)
            del self.choosy_counter[job_id]


    def register_ack(self, accept_task_list):
        if accept_task_list:
            for job_id in accept_task_list:
                if job_id in self.job_demand:
                    self.job_demand[job_id] -= 1
                    self.choosy_counter[job_id] += 1

    def schedule_task(self, client):
        task_list = []
        # print(f"Job deadline: {self.job_deadline}")
        # IRS heuristic
        sorted_jobid = sorted(self.choosy_counter)
        for job_id in sorted_jobid:
            if self.job_demand[job_id] > 0 and self.job_eligibility[job_id] in client.eligibility:
               task_list.append(job_id)

        random.shuffle(task_list)
        return task_list

    def register_job(self, job_id, request, time):
        if job_id not in self.removed_job:
        # assert job_id not in self.removed_job
            if request.amount == 1:
                self.job_demand[job_id] += 1  # where to clean up the demand for apple and google
            else:
                self.job_demand[job_id] = request.amount

class ShortestScheduler(VennScheduler):
    def punch_job(self, job_id, job_dict):
        self.job_total_round[job_id] = job_dict['total_round']
        self.job_eligibility[job_id] = job_dict['eligibility']
        self.job_init_size[job_id] = job_dict['amount']
        self.job_est_duration[job_id] = job_dict['deadline'] if job_dict['deadline'] > 0 else 3 * self.job_init_size[
                                                                                                        job_id]
    def register_ack(self, accept_task_list):
        if accept_task_list:
            for job_id in accept_task_list:
                if job_id in self.job_demand:
                    self.job_demand[job_id] -= 1

    # Shortest first
    def _cal_irs_score(self, job_id): #
        return self.job_total_round[job_id] * self.job_est_duration[job_id]

    def register_round_stats(self, job_id, end, time, success):
        # Record job round duration/size; round completion / model update; update job score
        if success:
            self.job_total_round[job_id] -= 1
            self.job_end_time[job_id].append(time)
            self.job_est_duration[job_id] = (self.job_end_time[job_id][-1] - self.job_end_time[job_id][0]) / (len(self.job_end_time[job_id])-1)

        if end:
            # print(f"Finish and remove job {job_id}")
            del self.job_demand[job_id]
            del self.job_score[job_id]
            self.removed_job.add(job_id)

    def register_job(self, job_id, request, time):
        # Record and detect job request pattern
        if job_id not in self.job_end_time:
            # initialize score; unknown duration
            # TODO: how to know shortest without profiling
            # avg_duration = sum(self.job_est_duration.values()) / len(self.job_est_duration) if len(self.job_est_duration) > 0 else 60
            # self.job_est_duration[job_id] = avg_duration
            self.job_end_time[job_id].append(time)
            self.job_score[job_id] = self._cal_irs_score(job_id)

        # assert job_id not in self.removed_job
        if job_id not in self.removed_job:
            if request.amount == 1:
                self.job_demand[job_id] += 1 # where to clean up the demand for apple and google
            else:
                self.job_demand[job_id] = request.amount
                self._cal_job_scores()
                self._cal_job_order()


    def schedule_task(self, client):
        task_list = []
        # print(f"Job deadline: {self.job_deadline}")
        # IRS heuristic
        for job_id in self.job_order:
            if self.job_demand[job_id] > 0 and self.job_eligibility[job_id] in client.eligibility:
               task_list.append(job_id)

        return task_list

class PhoenixScheduler(VennScheduler):
    def punch_job(self, job_id, job_dict):
        self.job_total_round[job_id] = job_dict['total_round']
        self.job_eligibility[job_id] = job_dict['eligibility']
        self.job_init_size[job_id] = job_dict['amount']

    def register_ack(self, accept_task_list):
        if accept_task_list:
            for job_id in accept_task_list:
                if job_id in self.job_demand:
                    self.job_demand[job_id] -= 1

    # smallest first
    def _cal_irs_score(self, job_id): #
        return self.job_total_round[job_id] * self.job_init_size[job_id] / self.traffic[job_id]

    def register_round_stats(self, job_id, end, time, success):
        # Record job round duration/size; round completion / model update; update job score
        if success:
            self.job_total_round[job_id] -= 1
            # self.job_end_time[job_id].append(time)
            # self.job_est_duration[job_id] = (self.job_end_time[job_id][-1] - self.job_end_time[job_id][0]) / (len(self.job_end_time[job_id])-1)

        if end:
            # print(f"Finish and remove job {job_id}")
            del self.job_demand[job_id]
            del self.job_score[job_id]
            self.removed_job.add(job_id)

    def register_job(self, job_id, request, time):
        self.traffic[job_id] = self._cal_client_traffic(job_id) # use average traffic instead ?
        # Record and detect job request pattern
        if job_id not in self.job_demand:
            # initialize score; unknown duration
            # avg_duration = sum(self.job_est_duration.values()) / len(self.job_est_duration) if len(self.job_est_duration) > 0 else 60
            # self.job_end_time[job_id].append(time)
            self.job_score[job_id] = self._cal_irs_score(job_id)


        # assert job_id not in self.removed_job
        if job_id not in self.removed_job:
            if request.amount == 1:
                self.job_demand[job_id] += 1 # where to clean up the demand for apple and google
            else:
                self.job_demand[job_id] = request.amount
                self._cal_job_scores()
                self._cal_job_order()


    def schedule_task(self, client):

        for e in client.eligibility:
            self.checkin_window[e].append(client.time)

        task_list = []
        # print(f"Job deadline: {self.job_deadline}")
        # IRS heuristic
        for job_id in self.job_order:
            if self.job_demand[job_id] > 0 and self.job_eligibility[job_id] in client.eligibility:
               task_list.append(job_id)

        return task_list

    def _cal_job_scores(self):
        for job_id in self.job_demand:
            self.job_score[job_id] = self._cal_irs_score(job_id)

 