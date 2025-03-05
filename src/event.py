

# import pandas as pd
# import numpy as np
# import random
# import os, pickle
import heapq
import sys
# import time
from datetime import datetime
import json

from util import Event, Request
from job import *
# Job, AgnosticJob, GoogleJob, DecentralizedJob, AppleJob, PapayaJob, DecPapayaJob
from client import *
# Client, AgnosticClient, FIFOClient, GoogleClient
from scheduler import *
# Scheduler, MetaScheduler, AppleScheduler, FIFOScheduler, \
# AmountScheduler, DiffiScheduler,WorkloadScheduler, DeadlineScheduler,\
# FailureScheduler, HeterScheduler, UrgencyScheduler, TrafficScheduler, \
# MixScheduler, FreqScheduler, TrafficDiffiScheduler, PapayaScheduler, \
# NaiveScheduler
from plot import *
import matplotlib.pyplot as plt
from setup_config import *


def simulate_centralized(state, eligibility, sched, job_type, client_type ):
    random.seed(RANDOMSEED)
    np.random.seed(RANDOMSEED)
    # meta OR apple
    event_pq = []
    num_job = NUM_JOB
    num_day = NUM_DAY
    succeed_client = 0
    fail_client_timestamp = []
    waiting_client_timestamp = []
    print("Push client checkin event")
    client_event_list = load_device_state(state, eligibility, client_type, num_day)
    event_pq += client_event_list
    print("Push job request event")
    request_list, job_list, job_request_list = generate_job_request(num_job, job_type, num_day)
    event_pq += request_list
    heapq.heapify(event_pq)

    print("Init central scheduler")
    scheduler = eval(sched)(num_job)

    for job in job_list:
        job_dict = { 'total_round': job.round, 'eligibility': job.requirement,
                     'deadline':job.duration, 'workload': job.workload,
                     'amount': job.amount}
        scheduler.punch_job(job.id, job_dict)

    while event_pq:
        event = heapq.heappop(event_pq)
        event_type = event.type
        # JOB
        if event_type == 'START' :
            job_id = event.obj_id
            # job_demand_list[job_id] = True

            scheduler.register_job(job_id, event.msg, job_list[job_id].job_type)

        # CLIENT
        elif event_type == 'CHECKIN':
            client_id = event.obj_id
            client = event.msg
            checkin_time = event.time
            sched_task_list = scheduler.schedule_task(client)
            if sched_task_list:
                # if agnostic: # offer
                dispatch_noise = random.uniform(0, 2)  # hardcode
                checkin_time += dispatch_noise
                heapq.heappush(event_pq, Event(checkin_time, 'ASSIGN', sched_task_list, client))
            else:
                waiting_client_timestamp.append(checkin_time)

        elif event_type == 'ASSIGN':
            job_id_list = event.obj_id
            client = event.msg
            accept_task_list = client.assign( event.time, job_id_list,
                                              [job_request_list[task_id].workload for task_id in job_id_list],
                                              [job_request_list[task_id].comm for task_id in job_id_list])
            scheduler.register_ack(accept_task_list)
            cur_time = event.time
            if accept_task_list:
                # print(accept_task_list)
                for task_id in accept_task_list: # assume sequential
                    finish_time = client.execute( cur_time,
                                                job_request_list[task_id].workload,
                                                job_request_list[task_id].comm)
                    if (finish_time > 0 and job_type not in async_job) or \
                        (job_type in async_job and 0 < finish_time < cur_time + job_list[task_id].timeout ):
                        heapq.heappush(event_pq, Event( finish_time, 'FINISH',
                                                        task_id, job_list[task_id].virtual_round ))
                        # print(f"[{finish_time}s] Client {client.id} execute task {task_id}")
                        cur_time = finish_time
                        succeed_client += 1
                    else:
                        if job_type in async_job: # for device failure
                            heapq.heappush(event_pq, Event(cur_time + job_list[task_id].duration, 'FAIL',
                                                           task_id, job_list[task_id].round_num))
                        fail_client_timestamp.append(cur_time + job_list[task_id].duration)
                        # print(f'Client {client.id} time out at time {finish_time}>{cur_time} + {job_list[task_id].duration}' )
                        break

        elif event_type == 'FAIL':
            # for papaya failure detection
            job_id = event.obj_id

            new_event = job_list[job_id].resume_round_event(event.time)
            for e in new_event:
                heapq.heappush(event_pq, e)

        elif event_type == 'FINISH' :
            job_id = event.obj_id
            round_id = event.msg
            new_event = job_list[job_id].receive_result(event.time, round_id)
            if new_event: # incremental request for async; apple job
                for e in new_event:
                    heapq.heappush(event_pq, e)
            # print(f"[{event.time}s] Client {client.id} finish task {task_id}")

        elif event_type == 'CLEAR':
            job_id = event.obj_id
            scheduler.clear_demand(job_id)

        elif event_type == 'CLOSE':
            job_id = event.obj_id
            success, end = job_list[job_id].close_round(event.time)
            scheduler.register_round_stats(job_id, end, event.time, success)
            if not success:
                new_rounds_event = job_list[job_id].resume_round_event(event.time+0.1)
                for new_event in new_rounds_event:
                    heapq.heappush(event_pq, new_event)

        elif event_type == 'END':
            print("====== Reach the end of the simulation ======")
            break

    res_str = show_state(job_list)
    goodput_rate = succeed_client / max(1, len(fail_client_timestamp) + succeed_client)
    goodput_rate_str = f'Goodput rate {goodput_rate}'
    res_str += goodput_rate_str

    print(f"{sys.argv[1:]} Client failure/infeasible rate {len(fail_client_timestamp) / max(1, len(fail_client_timestamp) + succeed_client)}")
    visualize_result([job.acc_res for job in job_list],
                     [job.acc_res_timestamp for job in job_list],
                     [job.straggler_timestamp for job in job_list],
                     fail_client_timestamp, waiting_client_timestamp,
                     [job.abort_timestamp for job in job_list],
                     [job.complete_timestamp for job in job_list],
                     [job.round_timestamp for job in job_list],
                     [[job.start, job.job_finsh_time] for job in job_list],
                     res_str)


def visualize_result(acc_job_res, acc_job_res_time, straggler_time, failure_time, waiting_time, abort_time, complete_time, round_time, job_duration, res_str ):
    plt.rcParams["figure.figsize"] = [12, 12]
    plt.rcParams["figure.autolayout"] = True
    plt.subplot(2, 2, 1)
    plot_progress(acc_job_res, acc_job_res_time, sys.argv[1:5])
    plt.subplot(2, 2, 2)
    plot_client_utilization(acc_job_res_time, straggler_time, failure_time, waiting_time, abort_time, complete_time, sys.argv[1:5])
    plt.subplot(2, 2, 3)
    # plot_client_utilization([acc_job_res_time[0]], [straggler_time[0]], failure_time, waiting_time, [abort_time[0]], [complete_time[0]], sys.argv[1:])
    plot_round_completion(round_time)
    plt.subplot(2, 2, 4)
    plot_job_online(job_duration)
    # plot_request_rate(job_duration )
    # plt.text(0, 8, res_str)
    plt.show()
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    os.makedirs('fig', exist_ok=True)
    file_name = f'fig/{sys.argv[1:5]}_{sys.argv[5][7:]}_{res_str}.png'
    with open('logging.txt', 'a') as file:
        file.write(f'[{current_time}]: {file_name}\n')

    plt.savefig(file_name)

def show_state(job_list):
    failure_rate = []
    num_waste = 0
    success_rate = []
    valid_res_rate = []
    job_completion_weighted = 0
    jct_list = []
    num_straggler = 0
    total_res_num = 0
    request_completion_time = []
    queue_delay = []
    for job in job_list:
        failure, waste, valid_result_per_hour, success, \
                    completed_request, jct, straggler_t, total_res, rct_list = job.show_stats()
        failure_rate.append(failure)
        num_waste += waste
        request_completion_time += rct_list
        num_straggler += len(straggler_t)
        success_rate.append(success)
        valid_res_rate.append(valid_result_per_hour)
        job_completion_weighted += completed_request
        total_res_num += total_res
        queue_delay += job.queuing_delay_list

        if jct > 0:
            jct_list.append(jct)
    job_completion_weighted /= sum([job.round for job in job_list])
    avg_request_completion_time = np.mean(request_completion_time)
    rct_str = f'RCT: {round(avg_request_completion_time,3)}; '

    jct_str = ''
    makespan_str = ''
    jcr_str = f'JCR: { round(np.mean(success_rate),3) }; '
    if len(jct_list) > 0:
        jct_str = f"JCT: { round(np.mean(jct_list),3)}; "
        makespan_str = f'Makespan: {round(max(jct_list),3)}; '
    waste_str = f"Waste(%): {round(num_waste / total_res_num,3)}; "
    straggler_str = f"Straggler(%): { round(num_straggler / total_res_num,3)}; "
    rcr_str = f'RCR: {round(job_completion_weighted,3)}; '
    queue_delay_str = f'Queuing(s): {round(np.mean(queue_delay),3)}; '

    print(# f"Job round success rate: {np.mean(failure_rate)}; "
          f"Job completion rate ({NUM_DAY * NUM_WEEK} days) {np.mean(success_rate)}; "
          + queue_delay_str + jct_str + rct_str +
          f"Valid result rate {np.mean(valid_res_rate)}; "
          f"Request completion rate {job_completion_weighted};"
          f" Total response: {total_res_num} "
          + waste_str + straggler_str)

    return queue_delay_str + rcr_str + rct_str + jcr_str + jct_str + makespan_str + waste_str + straggler_str

if __name__ == '__main__':

    simulate_centralized(state=client_file, eligibility=eligibility_file, sched=sys.argv[1], job_type = sys.argv[2], client_type = sys.argv[3])




