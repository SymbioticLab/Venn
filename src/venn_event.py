
from event import *
from baseline import *
from log import get_logger

event_logger = get_logger('Event')


def simulate_venn_event(state, eligibility, sched, job_type, client_type ):
    random.seed(RANDOMSEED)
    np.random.seed(RANDOMSEED)
    # meta OR apple
    event_pq = []
    num_job = NUM_JOB
    num_day = NUM_DAY
    succeed_client = 0
    fail_client_timestamp = []
    waiting_client_timestamp = []
    event_logger.info("Push client checkin event")
    client_event_list = load_device_state(state, eligibility, client_type, num_day)
    event_pq += client_event_list
    event_logger.info("Push job request event")
    request_list, job_list, job_request_list = generate_job_request(num_job, job_type, num_day)
    event_pq += request_list
    heapq.heapify(event_pq)

    event_logger.info("Init central scheduler")
    scheduler = eval(sched)(num_job)
    punch_job_list = []

    request_rate_logging = defaultdict(list)
    while event_pq:
        event = heapq.heappop(event_pq)
        event_type = event.type
        # JOB
        if event_type == 'START' :
            job_id = event.obj_id
            if job_id not in punch_job_list:
                job = job_list[job_id]
                job_dict = {'total_round': job.round, 'eligibility': job.requirement,
                            'deadline': job.duration, 'workload': job.workload,
                            'amount': job.amount, 'buffer_size': job.buffer_size}
                scheduler.punch_job(job.id, job_dict)
                punch_job_list.append(job_id)

            # job_demand_list[job_id] = True
            scheduler.register_job(job_id, event.msg, event.time)
            request_rate_logging[job_id] += event.msg.amount * [event.time]

        # CLIENT
        elif event_type == 'CHECKIN':
            # client_id = event.obj_id
            client = event.msg
            checkin_time = event.time
            sched_task_list = scheduler.schedule_task(client)
            # event_logger.info(f"Schedule {sched_task_list} to client {client.id}")
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

            cur_time = event.time
            if accept_task_list:
                # event_logger.info(accept_task_list)
                for task_id in accept_task_list: # assume sequential
                    new_event = job_list[task_id].dispatch(cur_time)
                    scheduler.register_ack([task_id])
                    # event_logger.info(f"Dispatch {task_id} to client {client.id}")
                    if new_event: # new request upon dispatch
                        for e in new_event:
                            heapq.heappush(event_pq, e)

                    finish_time = client.execute( cur_time,
                                                job_request_list[task_id].workload,
                                                job_request_list[task_id].comm)
                    if (finish_time > 0 and job_type not in async_job) or \
                        (job_type in async_job and 0 < finish_time < cur_time + job_list[task_id].timeout ):
                        heapq.heappush(event_pq, Event( finish_time, 'FINISH',
                                                        task_id, job_list[task_id].virtual_round ))
                        # event_logger.info(f"[{finish_time}s] Client {client.id} execute task {task_id}")
                        succeed_client += 1

                        cur_time = finish_time
                    else:
                        if job_type in async_job: # for device failure
                            heapq.heappush(event_pq, Event(cur_time + job_list[task_id].duration, 'FAIL',
                                                           task_id, job_list[task_id].round_num))
                        fail_client_timestamp.append(cur_time + job_list[task_id].duration)
                        # event_logger.info(f'Client {client.id} time out at time {finish_time}>{cur_time} + {job_list[task_id].duration}' )
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

        elif event_type == 'CLEAR':
            job_id = event.obj_id
            scheduler.clear_demand(job_id)

        elif event_type == 'CLOSE':
            job_id = event.obj_id
            success, end, new_rounds_event = job_list[job_id].close_round(event.time)
            if end is not None and success is not None:
                scheduler.register_round_stats(job_id, end, event.time, success)
            if new_rounds_event:
                for new_event in new_rounds_event:
                    heapq.heappush(event_pq, new_event)

        elif event_type == 'END':
            event_logger.info(f"====== Reach the end {event.time} of the simulation ======")
            break

    res_str = show_state(job_list)

    goodput_rate = round(succeed_client / max(1, len(fail_client_timestamp) + succeed_client),4)
    goodput_rate_str = f'Goodput rate {goodput_rate}, '
    res_str += goodput_rate_str
    event_logger.info(f"{sys.argv[1:]} Client failure/infeasible rate { len(fail_client_timestamp) / max(1, len(fail_client_timestamp) + succeed_client)}")

    visualize_result([job.acc_res for job in job_list],
                     [job.acc_res_timestamp for job in job_list],
                     [job.straggler_timestamp for job in job_list],
                     fail_client_timestamp, waiting_client_timestamp,
                     [job.abort_timestamp for job in job_list],
                     [job.complete_timestamp for job in job_list],
                     [job.round_timestamp for job in job_list],
                     [[job.start, job.job_finsh_time] for job in job_list],
                     res_str) 
    
if __name__ == '__main__':

    simulate_venn_event(state=client_file, eligibility=eligibility_file, sched=sys.argv[1], job_type = sys.argv[2], client_type = sys.argv[3])




