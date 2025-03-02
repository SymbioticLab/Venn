from event import *


def simulate_decentralized(state, eligibility, sched, job_type, client_type):
    random.seed(RANDOMSEED)
    np.random.seed(RANDOMSEED)
    # Google
    event_pq = []

    succeed_client = 0
    fail_client_timestamp = []
    waiting_client_timestamp = []
    num_day = NUM_DAY
    num_job = NUM_JOB
    #  init client checkin into event queue + eligibility + state + capacity
    print("Push client checkin event")
    client_event_list = load_device_state(state, eligibility, client_type, num_day)
    event_pq += client_event_list

    print("Push job request event")
    request_list, job_list, job_request_list = generate_job_request(num_job, job_type, num_day)

    event_pq += request_list

    heapq.heapify(event_pq)
    job_demand_list = {} # [ False for _ in range(num_job)]
    print("Start simulation")
    while event_pq:
        event = heapq.heappop(event_pq)
        event_type = event.type
        # JOB
        if event_type == 'START' :
            job_id = event.obj_id
            job_demand_list[job_id] = True

        # CLIENT
        elif event_type == 'CHECKIN':
            client = event.msg
            checkin_time = event.time
            if sum(job_demand_list.values())==0:
                waiting_client_timestamp.append(checkin_time)
                continue
            for job_id, job in enumerate(job_list):
                if job_id in job_demand_list and job_demand_list[job_id]:
                    dispatch_event, demand_bool = job.select(checkin_time, client)
                    if dispatch_event:
                        heapq.heappush(event_pq, dispatch_event)
                        job_demand_list[job_id] = demand_bool

        elif event_type == 'DISPATCH':
            job_id = event.obj_id
            client_assign_queue = job_list[job_id].dispatch(event.time)
            if client_assign_queue:
                # print(f"[{event.time}s]>>>>> Job {job_id} dispatch tasks")
                for event in client_assign_queue:
                    heapq.heappush(event_pq, event)
            else:
               # not enough clients check in --> abort directly
               #  print(f"[Time: {event.time}] Not enough check-in clients --> abort")
                pass

        elif event_type == 'CLOSE':
            job_id = event.obj_id
            success, end = job_list[job_id].close_round(event.time)
            if not success:
                new_rounds_event = job_list[job_id].resume_round_event(event.time)
                for new_event in new_rounds_event:
                    heapq.heappush(event_pq, new_event)
            if end:
                del job_demand_list[job_id]

        elif event_type == 'ASSIGN':
            job_id_list = event.obj_id
            client = event.msg
            # print(f"[{event.time}s]>>>>> Job {job_id_list} dispatch to Client {client.id}")

            accept_task_list = client.assign( event.time, job_id_list,
                                              [job_request_list[task_id].workload for task_id in job_id_list],
                                              [job_request_list[task_id].comm for task_id in job_id_list])
            cur_time = event.time
            if accept_task_list: # size = 1 for googleClient
                # print(accept_task_list)
                for task_id in accept_task_list: # assume sequential
                    finish_time = client.execute(  cur_time,
                                                job_request_list[task_id].workload,
                                                job_request_list[task_id].comm)
                    # print(f"[{cur_time}s] Client {client.id} execute {client.task_order}th task id:{task_id} ")

                    if job_type in async_job and  finish_time > cur_time + job_request_list[task_id].duration:
                        heapq.heappush(event_pq, Event(cur_time + job_list[task_id].duration, 'FAIL',
                                                       task_id, job_list[task_id].round_num))
                        break
                    elif finish_time > 0:
                        heapq.heappush(event_pq, Event( finish_time, 'FINISH',
                                                        task_id, job_list[task_id].virtual_round ))
                        # print(f"[{cur_time+duration}s] Client {client.id} execute task {task_id}")
                        cur_time = finish_time
                        succeed_client += 1
                    elif finish_time == -1:
                        fail_client_timestamp.append(event.time)
                        break
                    else:
                        # multiple tasks per device doesn't count to failure
                        break
            elif job_type in async_job: # async request ignore by the busy client
                for task_id in job_id_list:
                    heapq.heappush(event_pq, Event(event.time + job_list[task_id].duration, 'FAIL',
                                                   task_id, job_list[task_id].round_num))


        elif event_type == 'FAIL':
            # for papaya failure detection
            job_id = event.obj_id
            fail_client_timestamp.append(event.time)
            new_event = job_list[job_id].resume_round_event(event.time)
            for e in new_event:
                heapq.heappush(event_pq, e)

        elif event_type == 'FINISH' :
            job_id = event.obj_id
            round_id = event.msg
            close_event = job_list[job_id].receive_result(event.time, round_id)
            if close_event:
                for e in close_event:
                    heapq.heappush(event_pq, e)

        elif event_type == 'END':
            print("====== Reach the end of the simulation ======")
            break

    res_str = show_state(job_list)
    print(f"{sys.argv[1:]} Client failure/infeasible rate {len(fail_client_timestamp) / max(1, len(fail_client_timestamp) + succeed_client)}")

    visualize_result([job.acc_res for job in job_list],
                     [job.acc_res_timestamp for job in job_list],
                     [job.straggler_timestamp for job in job_list],
                     fail_client_timestamp, waiting_client_timestamp,
                     [job.abort_timestamp for job in job_list],
                     [job.complete_timestamp for job in job_list],
                     [job.round_timestamp for job in job_list],
                     [[job.start, job.job_finsh_time] for job in job_list], res_str )


if __name__ == '__main__':
    simulate_decentralized(state=client_file, eligibility=eligibility_file, sched=sys.argv[1], job_type = sys.argv[2], client_type = sys.argv[3])
