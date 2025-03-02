
import matplotlib.pyplot as plt
import numpy as np
from setup_config import *
from scipy import stats


def plot_device_cap_distribution():
    client_capacity = load_device_capacity()
    x = [client_capacity[clt]['communication'] for clt in client_capacity ][:10000]
    y = [client_capacity[clt]['computation'] for clt in client_capacity ][:10000]
    xy = np.vstack([x,y])
    z = stats.gaussian_kde(xy)(xy)

    # Sort the points by density, so that the densest points are plotted last
    idx = z.argsort()
    x, y, z = np.array(x)[idx], np.array(y)[idx], np.array(z)[idx]

    plt.scatter(x, y, c=z, s=10)
    plt.title('Device Capacity Distribution')
    plt.ylabel(f'Computation latency')
    plt.xlabel('Communication bandwidth')
    plt.show()
    plt.savefig(f'fig/device_dist.png')

# plot_device_cap_distribution()

def plot_utilization(start_end_list, file_name = None):
    # start_end_list.sort(key=lambda x: x[0])
    max_len = 86400
    res = [0 for _ in range(max_len)]
    for interval in start_end_list:
        start, end = interval[0], min(interval[1], max_len)
        for i in range(start, end):
            res[i] += 1
    if file_name:
        with open(f'{file_name}.txt', 'a') as f:
            f.write(str(res))
            f.write('\n')

    plt.plot(res)
    plt.xlim([0, 86400])  # adjust the right leaving left unchanged
    plt.title(file_name)
    plt.ylabel('Utilization')
    plt.show()


def plot_jobs_progress(results_ends, file_name=None):
    for results_end in results_ends:
        max_len = max(results_end) + 1
        res = [0 for _ in range(max_len)]
        for i in results_end:
            res[i] += 1
        acc_res = np.cumsum(res)
        if file_name:
            with open(f'{file_name}_accumulate.txt', 'a') as f:
                f.write(str(list(acc_res)))
                f.write('\n')
        plt.plot(acc_res)
    plt.title(file_name)
    plt.xlim([0, 86400])  # adjust the right leaving left unchanged
    plt.ylabel('Accumulated results')
    plt.show()

def plot_job_progress(results_end, file_name=None):
    max_len = max(results_end)+1
    res = [0 for _ in range(max_len)]
    for i in results_end:
        res[i] += 1
    acc_res = np.cumsum(res)
    if file_name:
        with open(f'{file_name}.txt', 'a') as f:
            f.write(str(list(acc_res)))
            f.write('\n')
    plt.plot(acc_res)
    plt.xlim([0, 86400])  # adjust the right leaving left unchanged
    plt.title(file_name)
    plt.ylabel('Accumulated results')
    plt.xlabel('Time')
    plt.show()

import time

def plot_round_completion(round_time, window = 3600, days = NUM_DAY*NUM_WEEK):
    plt.hist([item for sublist in round_time for item in sublist], bins = 86400 * days // window, range = (0,  86400 * days ) )

    plt.title('Round completion rate')
    plt.ylabel(f'Rounds / {window//60}min')
    plt.xlabel('Time')
    plt.ylim([0, 200])  # adjust the right leaving left unchanged
    # plt.xlim([0, 1.8e6])

def plot_request_rate(request_rate, window = 3600, days = NUM_DAY*NUM_WEEK):
    n, bins, patches = plt.hist( request_rate, bins = 86400 * days // window, range = (0,  86400 * days )  )
    print("Request rate: ", n)
    plt.title('Resource Request Rate')
    plt.ylabel(f'#Devices / {window//3600} hr')
    plt.xlabel('Time')
    # plt.ylim([0, 1500])  # adjust the right leaving left unchanged
    plt.xlim([0, 1.8e6]) # TODO: start and end of the job

def plot_round_duration_dist(round_timestamp_list, window = 60, days = NUM_DAY*NUM_WEEK):
     # for job_round_ts in round_timestamp_list:
    round_duration_list = [(round_timestamp_list[i]-round_timestamp_list[i-1] )/ window for i in range(1, len(round_timestamp_list)) ]
    sampled_duration = random.sample(round_duration_list, min(100, len(round_duration_list)))
    print("Round duration pdf: ", sampled_duration )
    round_duration_list = sorted(sampled_duration)
    df_mean = np.mean(round_duration_list)
    df_std = np.std(round_duration_list)
    pdf = stats.norm.pdf(round_duration_list, df_mean, df_std)
    plt.plot(round_duration_list, pdf)

    # n, bins, patches = plt.hist(round_duration_list, bins=100 )

    plt.title('Round Duration Distribution')
    plt.ylabel(f'PDF')
    plt.xlabel('Round Duration (min)')
    # plt.ylim([0, 1500])  # adjust the right leaving left unchanged
    # plt.xlim([0, 1.8e6]) # TODO: start and end of the job


def plot_job_online(job_duration):
    x = []
    y = []
    start_list = sorted([j[0] for j in job_duration])
    end_list = sorted([j[1] for j in job_duration if j[1]>0])
    num_job = 0
    i = j = 0
    while i < len(start_list) or j < len(end_list):
        if (i < len(start_list) and j < len(end_list) and start_list[i] < end_list[j]) or j == len(end_list):
            num_job+=1
            x.append(start_list[i])
            y.append(num_job)
            i+=1
        else:
            num_job -= 1
            x.append(end_list[j])
            y.append(num_job)
            j+=1

    # plt.xlim([0, 1.8e6])
    plt.plot(x, y)
    plt.title('Online Jobs')
    plt.ylabel(f'Number of online Jobs')
    plt.xlabel('Time')


def plot_client_utilization(success_response_time, straggler_response_time, failure_response_time,
                            waiting_time, abort_time, complete_time, file_name=None, window = 3600, days = NUM_DAY*NUM_WEEK):
    # contains abort & non-straggler response
    num_bins= 86400 * days // window
    if len(abort_time[0])> 0 or len(complete_time[0]) > 0:
        plt.hist([item for sublist in abort_time for item in sublist], bins=num_bins, range = (0, 86400*days),
                 color='grey', label='Abort', alpha = 0.5)  # only google
        plt.hist([item for sublist in complete_time for item in sublist], bins =num_bins, range = (0, 86400*days),
                 color = 'green' , label='Complete', alpha = 0.5) # only google
    else:
        plt.hist([item for sublist in success_response_time for item in sublist], bins=num_bins, range = (0, 86400*days),
                 color='green', label='Success', alpha = 0.5)

    plt.hist([item for sublist in straggler_response_time for item in sublist], bins = num_bins, range = (0, 86400*days),
             color = 'orange', label='Straggler', alpha = 0.5 )
    plt.hist(failure_response_time, bins = num_bins ,range = (0, 86400*days), color ='red', label='Failure', alpha = 0.5)
    plt.hist(waiting_time, bins =num_bins , range = (0, 86400*days), color ='blue', label='Waiting', alpha = 0.1)

    plt.legend()
    plt.ylim([0, 35000])  # adjust the right leaving left unchanged
    plt.title(file_name)
    plt.ylabel(f'Clients / {window//60} min')
    plt.xlabel('Time')
    # plt.xlim(left=60)

def plot_progress(acc_job_res, acc_job_res_time, file_name=None ):
    for i, (acc_res, acc_res_time) in enumerate(zip(acc_job_res, acc_job_res_time)):
        plt.plot( acc_res_time, acc_res, label= f"Job {i}")
    # plt.xlim([0, 1.8e6])  # adjust the right leaving left unchanged
    plt.title(file_name)
    plt.ylabel('Accumulated results')
    plt.xlabel('Time')
    # plt.savefig(f'{file_name}_{time.time()}.png')


#### Motivation figure bundle ####


def motivation_request_result(acc_job_res, acc_job_res_time, straggler_time, failure_time, waiting_time, abort_time, complete_time, request_rate, round_duration, res_str ):
    plt.rcParams["figure.figsize"] = [18, 12]
    plt.rcParams["figure.autolayout"] = True
    plt.subplot(2, 3, 1)
    plot_progress(acc_job_res, acc_job_res_time, sys.argv[1:5])
    plt.subplot(2, 3, 2)
    plot_client_utilization(acc_job_res_time, straggler_time, failure_time, waiting_time, abort_time, complete_time, sys.argv[1:5])
    plt.subplot(2, 3, 3)
    plot_request_rate(request_rate[0] )
    plt.subplot(2, 3, 4)
    plot_request_rate(request_rate[1] )
    plt.subplot(2, 3, 5)
    plot_request_rate(request_rate[2] )
    plt.subplot(2, 3, 6)
    plot_request_rate(request_rate[3] )
    # plt.text(0, 8, res_str)
    plt.show()
    plt.savefig(f'fig/{sys.argv[1:]}_{res_str}.png')



def motivation_duration_result(acc_job_res, acc_job_res_time, straggler_time, failure_time, waiting_time, abort_time, complete_time, request_rate, round_duration, res_str ):
    plt.rcParams["figure.figsize"] = [18, 12]
    plt.rcParams["figure.autolayout"] = True
    plt.subplot(2, 3, 1)
    plot_progress(acc_job_res, acc_job_res_time, sys.argv[1:5])
    plt.subplot(2, 3, 2)
    plot_client_utilization(acc_job_res_time, straggler_time, failure_time, waiting_time, abort_time, complete_time, sys.argv[1:5])
    plt.subplot(2, 3, 3)
    plot_round_duration_dist(round_duration[0] )
    if len(round_duration) > 1:
        plt.subplot(2, 3, 4)
        plot_round_duration_dist(round_duration[1] )
        plt.subplot(2, 3, 5)
        plot_round_duration_dist(round_duration[2] )
        plt.subplot(2, 3, 6)
        plot_round_duration_dist(round_duration[3] )
    # plt.text(0, 8, res_str)
    plt.show()
    plt.savefig(f'fig/{sys.argv[1:]}_{res_str}.png')
