import logging

from job import Job
from util import Request, Event

class GoogleJob(Job):
    def __init__(self, id, job_type, request, round, start, buffer_size):
        Job.__init__(self, id, job_type, request, round, start)
        self.tmp_dispatch = 0
        self.close_time_dict = {}
        self.start_time_dict = {}
        # TODO: implement for other job types
        self.queuing_delay_list = []

    def dispatch(self, dispatch_time):
        self.tmp_dispatch += 1
        if self.tmp_dispatch == self.request.amount * self.fraction:
            self.queuing_delay_list.append(dispatch_time - self.start_time_dict[self.virtual_round])

    def close_round(self, time):
        if (self.virtual_round in self.close_time_dict and self.close_time_dict[self.virtual_round][-1] == time):
            success = False
            end = self.job_finsh_time > 0

            if self.tmp_dispatch >= self.amount * self.fraction and \
                    self.round_res_count[-1] >= min(self.tmp_dispatch, self.amount) * self.fraction:
                self.round_timestamp.append(time)
                self.round_num += 1
                if self.round_num >= self.round:
                    self.job_finsh_time = time
                    end = True
                success = True
                self.complete_timestamp += self.acc_res_timestamp[-self.round_res_count[-1]:]
                print(f"[Time({time}) JOB{self.id}] Proceed to round {self.round_num } with {self.round_res_count[-1]} results")
            else: # abort
                self.wasted_res += self.round_res_count[-1]
                self.acc_res.append(self.acc_res[-1] - self.round_res_count[-1])
                self.acc_res_timestamp.append(time)
                self.abort_rounds += 1
                self.abort_timestamp += self.acc_res_timestamp[- max(self.round_res_count[-1], 1 ):-1]
                print(f"[Time({time}) JOB{self.id}] Fail at round {self.round_num} with {self.round_res_count[-1]}/{self.amount * self.fraction} results")
            self.round_res_count.append(0)
            self.virtual_round += 1
            self.tmp_dispatch = 0

            return success, end, None if end else self.resume_round_event(time)
        else:
            # fake close
            return None, None, None

    def receive_result(self, time, round):
        if round == self.virtual_round:
            self.round_res_count[-1] += 1
            self.acc_res_timestamp.append(time)
            self.acc_res.append(self.acc_res[-1]+1)
            # Allow more than needed; close immediately?
            if self.round_res_count[-1] >= self.amount * self.fraction:
                if len(self.close_time_dict[self.virtual_round]) == 1:
                    self.close_time_dict[self.virtual_round].append(time)
                    return [Event(time, 'CLOSE', self.id, None)]
        else:
            self.straggler_timestamp.append(time)
        return None

    def resume_round_event(self, time):
        self.close_time_dict[self.virtual_round] = [self.duration + time]
        self.start_time_dict[self.virtual_round] = [time]

        start = Event( time+0.1, 'START', self.id, self.request )
        close = Event( self.duration + time, 'CLOSE', self.id, None)


        return [start, close]

    def generate_round_event(self):
        return self.resume_round_event(self.start)


class PapayaJob(Job):
    # asynchronous job; send request incrementally;
    def __init__(self, id, job_type, request, round, start, buffer_size ):
        Job.__init__(self, id, job_type, request, round, start)
        self.buffer_size = buffer_size
        self.stale_num = 0
        self.timeout = 250
        self.amount = buffer_size # for calculate score with buffer size

    def show_request(self):
        print(f"=========== [JOB{self.id}] ===========")
        print(f"Request [Round: {self.round}]"
              f" [amount: {self.amount}]"
              f" [timeout: {self.duration}]"
              f" [buffer size: {self.buffer_size}] "
              f" [workload: {self.request.workload}]"
              f" [eligibility: {self.requirement}]")

    def resume_round_event(self, time):
        inc_request = Request(self.request.duration, 1, 1, self.request.workload, self.request.comm, self.requirement)
        start = Event(time + 0.1, 'START', self.id, inc_request)
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
            # new_events = []
            if self.round_res_count[-1] >= self.buffer_size:
                new_events = [Event(time, 'CLOSE', self.id, None)]
            else:
                new_events = self.resume_round_event(time)
            return new_events


    def close_round(self, time):
        self.round_num += 1
        # self.virtual_round += 1
        self.round_timestamp.append(time)

        if self.round_num == self.round:
            self.job_finsh_time = time
            self.end = True
            return True, True, None

        print(f"[Time({time}) JOB{self.id}] Proceed to round {self.round_num} with {self.round_res_count[-1]} results")
        self.round_res_count.append(0)

        return True, False, self.resume_round_event(time)

    def show_stats(self):
        self.show_request()
        job_completion_rate = self.round_num / self.round
        failure_rate = self.round_num/max(self.round_num+self.abort_rounds, 1)
        straggler_rate = len(self.straggler_timestamp ) / max(sum(self.round_res_count), 1) # contain these aborted res
        valid_result_per_hour = self.acc_res[-1] /( (self.acc_res_timestamp[-1]-self.acc_res_timestamp[0]+1)/3600)
        job_completion_time = self.job_finsh_time - self.start
        request_completion_time_list = [self.round_timestamp[i] - self.round_timestamp[i-1] for i in range(1, len(self.round_timestamp))]

        print(f"[JOB{self.id}] [Time {self.start} - {self.job_finsh_time}] finishes {self.round_num} ({job_completion_rate}) "
              f"rounds while aborts {self.abort_rounds} rounds ")
        print(f"[JOB{self.id}] Valid results per hour: {valid_result_per_hour}, "
              f"received {sum(self.round_res_count)} results with {len(self.straggler_timestamp )} stragglers.")
        print(f"[JOB{self.id}] Success round rate {failure_rate}; Straggler rate {straggler_rate}; "
              f"Staleness rate {self.stale_num/ max(1,sum(self.round_res_count))}")
        return failure_rate, 0, valid_result_per_hour, self.job_finsh_time > 0, self.round_num, job_completion_time, \
               self.straggler_timestamp , sum(self.round_res_count), request_completion_time_list
        # 2nd self.stale_num we do not care about the staleness for now

class AppleJob(Job):
    def __init__(self, id, job_type, request, round, start, buffer_size ):
        Job.__init__(self, id, job_type, request, round, start )
        self.tmp_response = 0
        self.cur_start_time = self.start
        self.workload = request.workload
        self.inc_request = Request(self.request.duration, 1, 1, self.request.workload, self.request.comm, self.requirement)

    def resume_round_event(self, time):
        start = Event(time, 'START', self.id, self.request)
        self.cur_start_time = time
        self.tmp_response = 0
        return [start]

    def generate_round_event(self):
        return self.resume_round_event(self.start)

    def dispatch(self, dispatch_time):
        if self.tmp_response <= -self.amount//2:
            # TODO: always block other jobs
            start = Event(dispatch_time + 0.1, 'START', self.id, self.inc_request )
            return [start]
        else:
            self.tmp_response -= 1
            return None

    def receive_result(self, time, round):
        if round == self.round_num:
            self.round_res_count[-1] += 1
            self.acc_res_timestamp.append(time)
            self.acc_res.append(self.acc_res[-1]+1)
            # Allow more than needed; close immediately?
            self.tmp_response += 1
            if self.round_res_count[-1] >= self.amount:
                return [Event(time, 'CLOSE', self.id, None)]
        else:
            self.straggler_timestamp.append(time)  # surplus response
        return None

    def close_round(self, time):
        self.round_num += 1
        self.virtual_round += 1
        self.round_timestamp.append(time)
        print( f"[Time({time}) JOB{self.id}] Proceed to round {self.round_num} with {self.round_res_count[-1]} results")
        self.round_res_count.append(0)

        if self.round_num >= self.round:
            self.job_finsh_time = time
            self.end = True
            return True, True, None
        else:
            return True, False, self.resume_round_event(time+0.1)
