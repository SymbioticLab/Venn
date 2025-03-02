from util import Request, Event
import random


class Job():
    # Google; abort; no selection window
    def __init__(self, id, job_type, request, round, start=0, buffer_size = 0 ):
        self.request = request # single config
        self.id = id
        self.job_type = job_type
        self.round = round
        self.duration = request.duration
        self.start = start
        self.fraction = request.fraction
        self.amount = self.demand = request.amount # assume equal amount per round
        self.requirement = request.eligibility + 1
        self.workload = request.workload

        self.round_timestamp = [start]
        self.straggler_timestamp = []
        self.abort_timestamp = []
        self.complete_timestamp = []
        self.acc_res_timestamp = [0] # success timestamp
        self.acc_res = [0] # [0, 1, 2, 3,...91, 92, ..., 155, 91, 92...]
        self.round_res_count = [0]
        self.round_num = 0
        self.abort_rounds = 0
        self.wasted_res = 0
        self.job_finsh_time = -1
        self.last_close_time = 0
        self.virtual_round = 0
        self.end = False
        self.buffer_size = buffer_size

    def show_request(self):
        print(f"=========== [JOB{self.id}] ===========")
        print(f"Request [Round: {self.round}]"
              f" [amount: {self.amount}]"
              f" [deadline: {self.duration}]"
              f" [min response: {self.fraction}] "
              f" [workload: {self.request.workload}]"
              f" [eligibility: {self.requirement}]"
              f" [fraction: {self.fraction}]")

    def resume_round_event(self, time):
        start = Event(self.last_close_time + 0.1, 'START', self.id, self.request )
        close = Event( self.duration + self.last_close_time , 'CLOSE', self.id, None)
        self.last_close_time += self.duration
        return [start, close]

    def generate_round_event(self):
        # init
        job_event = []
        for i in range(self.round):
            self.last_close_time = (i+1) * self.duration + self.start - 0.1
            job_event.append(Event(i * self.duration + self.start, 'START', self.id, self.request ))
            job_event.append(Event(self.last_close_time , 'CLOSE', self.id, None))

        return job_event

    def select(self, checkin_time, client):
        pass

    def dispatch(self, dispatch_time):
        pass

    def receive_result(self, time, round):
        # if round == self.round_num:
        if round == self.virtual_round:
            self.round_res_count[-1] += 1
            self.acc_res_timestamp.append(time)
            self.acc_res.append(self.acc_res[-1]+1)
        else:
            self.straggler_timestamp.append(time)
            # print(f"Job {self.id} ignore {self.round_res_count[-1]} results [{round}/{self.round_num}]")
        return None

    def close_round(self, time):
        success = False # self.retry < 0

        if self.round_res_count[-1] >= self.amount * self.fraction:
            self.round_timestamp.append(time)
            self.round_num += 1
            if self.round_num  == self.round:
                self.job_finsh_time = time
            else:
                print(f"[Time({time}) JOB{self.id}] Proceed to round {self.round_num } with {self.round_res_count[-1]} results")
            success = True
            self.complete_timestamp += self.acc_res_timestamp[-self.round_res_count[-1]:]
        else: # abort
            self.wasted_res += self.round_res_count[-1]
            self.acc_res.append(self.acc_res[-1] - self.round_res_count[-1])
            self.acc_res_timestamp.append(time)
            self.abort_rounds += 1
            self.abort_timestamp += self.acc_res_timestamp[- max(self.round_res_count[-1], 1 ):-1]
            print(f"[Time({time}) JOB{self.id}] Fail at round {self.round_num} with {self.round_res_count[-1]}/{self.amount * self.fraction} results")
        self.round_res_count.append(0)
        self.virtual_round += 1
        # success_round_rate = self.round_num / (self.round_num + self.abort_rounds)
        # second output will be sent to scheduler
        # indicate whether to remove the job demand from scheduler > 0; register failure rate info
        return success, self.job_finsh_time > 0

    def show_stats(self):
        self.show_request()
        job_completion_rate = self.round_num / self.round
        failure_rate = self.abort_rounds / max(self.round_num + self.abort_rounds, 1)
        waste_rate = (self.wasted_res) / max(sum(self.round_res_count), 1)
        straggler_rate = len(self.straggler_timestamp) / max(sum(self.round_res_count), 1) # contain these aborted res

        valid_result_per_hour = self.acc_res[-1] /( (self.acc_res_timestamp[-1]-self.acc_res_timestamp[0]+1)/3600)
        job_completion_time = self.job_finsh_time - self.start
        request_completion_time_list = [self.round_timestamp[i] - self.round_timestamp[i-1] for i in range(1, len(self.round_timestamp))]

        print(f"[JOB{self.id}] [Time {self.start} - {self.job_finsh_time}] finishes {self.round_num} ({job_completion_rate}) "
              f"rounds while aborts {self.abort_rounds} rounds ")
        print(f"[JOB{self.id}] Valid results per hour: {valid_result_per_hour}, "
              f"received {sum(self.round_res_count)} results with {len(self.straggler_timestamp)} stragglers.")
        print(f"[JOB{self.id}] Success round rate {failure_rate}; Straggler rate {straggler_rate}; Waste rate {waste_rate}")
        self.sup_print()
        return failure_rate, self.wasted_res, valid_result_per_hour, self.job_finsh_time > 0, self.round_num, job_completion_time, \
               self.straggler_timestamp, sum(self.round_res_count), request_completion_time_list

    def sup_print(self):
        pass

class AgnosticJob(Job):
    # for task offer & google's job
    def receive_result(self, time, round):
        # handle surplus offer -- response
        if round == self.virtual_round:
            if self.round_res_count[-1] < self.amount:
                self.round_res_count[-1] += 1
                self.acc_res.append(self.acc_res[-1] + 1)
                self.acc_res_timestamp.append(time)
            else:
                self.straggler_timestamp.append(time)
                print(f"[Job {self.id}] Dispatching more than need initially")
        else:
            self.straggler_timestamp.append(time)
            # print(f"Job {self.id} ignore {self.round_res_count[-1]} results [{round}/{self.round_num}]")
        return None

# class CenGoogleJob(AgnosticJob):
#     def resume_round_event(self, time):
#         start = Event(self.last_close_time + 0.1, 'START', self.id, self.request )
#         mid = Event( self.duration * 0.75 + self.last_close_time , 'CLEAR', self.id, None)
#         close = Event( self.duration + self.last_close_time , 'CLOSE', self.id, None)
#         self.last_close_time += self.duration
#         return [start, mid, close]
#
#     def generate_round_event(self):
#         # init
#         job_event = []
#         for i in range(self.round):
#             self.last_close_time = (i+1) * self.duration + self.start - 0.1
#             job_event.append(Event(i * self.duration + self.start, 'START', self.id, self.request ))
#             job_event.append(Event((i +  0.75) * self.duration + self.start, 'CLEAR', self.id, self.request ))
#             job_event.append(Event(self.last_close_time , 'CLOSE', self.id, None))
#
#         return job_event

class AppleJob(AgnosticJob):
    # don't abort round but keep receiving response util enough
    # generate new request once commit previous round
    def resume_round_event(self, time):
        # self.demand  = self.amount
        start = Event(time, 'START', self.id, self.request )
        return [start]

    def generate_round_event(self):
        # self.last_round_time = self.start
        return self.resume_round_event(self.start)

    def receive_result(self, time, round):
        if round == self.round_num:
            # self.demand -= 1
            self.round_res_count[-1] += 1
            self.acc_res_timestamp.append(time)
            self.acc_res.append(self.acc_res[-1]+1)
            # Allow more than needed; close immediately?
            if self.round_res_count[-1] >= self.amount:
                return [ Event(time, 'CLOSE', self.id, None)]
        else:
            self.straggler_timestamp.append(time)  # surplus response
            # print(f"Job {self.id} ignore {self.round_res_count[-1]} results [{round}/{self.round_num}]")
        return None

    def close_round(self, time):
        self.round_num += 1
        self.virtual_round += 1
        self.round_timestamp.append(time)
        print(
            f"[Time({time}) JOB{self.id}] Proceed to round {self.round_num} with {self.round_res_count[-1]} results")
        self.round_res_count.append(0)
        if self.round_num >= self.round:
            self.job_finsh_time = time
            return True, True
        else:
            # self.last_round_time = time
            # self.resume_round_event(time)
            return False, False

class DecAppleJob(AppleJob):
    def select(self, checkin_time, client):
        if self.requirement in client.eligibility:
            duration = self.request.workload * client.computation + self.request.comm / client.communication * 2
            if checkin_time + duration <= client.end:
                return Event(checkin_time+random.uniform(0, 0.5), 'ASSIGN', [self.id], client), self.demand > 0
        return None, True

class PapayaJob(Job):
    # asynchronous job; send request incrementally;
    def __init__(self, id, job_type, request, round, start, buffer_size ):
        Job.__init__(self, id, job_type, request, round, start, buffer_size )
        self.buffer_size = buffer_size
        self.stale_num = 0
        self.timeout = 250

    def show_request(self):
        print(f"=========== [JOB{self.id}] ===========")
        print(f"Request [Round: {self.round}]"
              f" [amount: {self.amount}]"
              f" [timeout: {self.timeout}]"
              f" [buffer size: {self.buffer_size}] "
              f" [workload: {self.request.workload}]"
              f" [eligibility: {self.requirement}]")

    def resume_round_event(self, time):
        inc_request = Request(self.request.duration, 1, 1, self.request.workload, self.request.comm, self.requirement)
        start = Event(time + 0.1, 'START', self.id, inc_request)
        self.demand += 1
        return [start]

    def generate_round_event(self):
        # init
        job_event = [Event(self.start, 'START', self.id, self.request)]
        return job_event

    def receive_result(self, time, round):
        if not self.end:
            self.stale_num += self.round_num - round
            self.round_res_count[-1] += 1
            self.acc_res_timestamp.append(time)
            self.acc_res.append(self.acc_res[-1] + 1)
            # new_events = None
            if self.round_res_count[-1] >= self.buffer_size:
                new_events = [Event(time, 'CLOSE', self.id, None)]
            else:
                new_events = self.resume_round_event(time)
            self.demand -= 1
            return new_events


    def close_round(self, time):
        self.round_num += 1
        self.virtual_round += 1
        self.round_timestamp.append(time)

        if self.round_num == self.round:
            self.job_finsh_time = time
            self.end = True
            return True, True

        print(f"[Time({time}) JOB{self.id}] Proceed to round {self.round_num} with {self.round_res_count[-1]} results")
        self.round_res_count.append(0)

        # TODO: detect current concurrency
        return False, False

    def show_stats(self):
        self.show_request()
        job_completion_rate = self.round_num / self.round
        failure_rate = self.abort_rounds / max(self.round_num + self.abort_rounds, 1)
        straggler_rate = len(self.straggler_timestamp ) / max(sum(self.round_res_count), 1) # contain these aborted res
        valid_result_per_hour = self.acc_res[-1] / ((self.acc_res_timestamp[-1]-self.acc_res_timestamp[0]+1)/3600)
        job_completion_time = self.job_finsh_time - self.start
        print(f"[JOB{self.id}] [Time {self.start} - {self.job_finsh_time}] finishes {self.round_num} ({job_completion_rate}) "
              f"rounds while aborts {self.abort_rounds} rounds ")
        print(f"[JOB{self.id}] Valid results per hour: {valid_result_per_hour}, "
              f"received {sum(self.round_res_count)} results with {len(self.straggler_timestamp )} stragglers.")
        print(f"[JOB{self.id}] Success round rate {failure_rate}; Straggler rate {straggler_rate}; Staleness rate {self.stale_num/ max(1,sum(self.round_res_count))}")
        return failure_rate, 0, valid_result_per_hour, self.job_finsh_time > 0, self.round_num, job_completion_time, self.straggler_timestamp , sum(self.round_res_count)
        # self.stale_num

class DecPapayaJob(PapayaJob):
    def select(self, checkin_time, client):
        # always have demand if count on the number of response
        if self.demand > 0 and self.requirement in client.eligibility:
            self.demand -= 1
            return Event(checkin_time+random.uniform(0, 0.5), 'ASSIGN', [self.id], client), self.demand > 0
        else:
            # do not execute client
            return None, self.demand > 0

class GoogleJob(Job):
    # have a selection window
    def __init__(self, id, job_type, request, round, start=0, buffer_size = 0 ):
        Job.__init__(self, id, job_type, request, round, start )
        self.client_pool = []
        self.selection_deadline = self.duration // 3
        self.discard_rounds = 0

    def select(self, checkin_time, client):
        if self.requirement in client.eligibility:
            self.client_pool.append(client)
            deadline = self.start + (self.round_num+self.discard_rounds+self.abort_rounds) * self.duration + self.selection_deadline
            if len(self.client_pool) >= self.amount or (checkin_time >= deadline):
                return Event(checkin_time+0.1, 'DISPATCH', self.id, None ), False
        return None, True

    def dispatch(self, time ):
        if len(self.client_pool) < self.amount * self.fraction:
            print(f"[Time {time}; Job {self.id}] {len(self.client_pool)} < {self.amount * self.fraction} Not enough check-in clients --> abort")
            self.client_pool = []
            self.discard_rounds += 1
            return None
        else:
            # print(f"{len(self.client_pool)} < {self.amount * self.fraction} Enough check-in clients --> start")
            client_list = random.sample(self.client_pool, min(len(self.client_pool), self.amount))
            self.client_pool = []
            event_queue = []
            for client in client_list:
                event_queue.append(Event(time + 2 - self.id , 'ASSIGN', [self.id], client))
                # event_queue.append(Event(time + random.uniform(0, 2), 'ASSIGN', [self.id], client))

            return event_queue

    def sup_print(self):
        print(f"Discard {self.discard_rounds} rounds with ratio {self.discard_rounds/max(1,self.round_num)}")

class DecentralizedJob(GoogleJob):
    # assume knowledge of additional eligibility

    def select(self, checkin_time, client):
        if self.requirement in client.eligibility:
            duration = self.request.workload * client.computation + self.request.comm / client.communication * 2
            if checkin_time + duration <= client.end:

                self.client_pool.append(client)
                deadline = self.start + (
                            self.round_num + self.discard_rounds + self.abort_rounds) * self.duration + self.selection_deadline

                if ( len(self.client_pool) >= self.amount)  or (checkin_time >= deadline) :

                    return Event(checkin_time+0.1, 'DISPATCH', self.id, None ), False

        return None, True
