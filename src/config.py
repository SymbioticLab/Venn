import yaml
from job import *
import pandas as pd
import numpy as np
import os, pickle
import sys
from util import Event, Request
from client import *
from src.venn import *
from src.venn_job import *
from src.venn_client import *


setup_file = str(sys.argv[5]) if len(sys.argv) > 5 else None
config = None
if setup_file:
    with open(setup_file, "r") as yamlfile:
        config = yaml.load(yamlfile, Loader=yaml.FullLoader)
        print("Read successful: ", config)

num_job = NUM_JOB = int(sys.argv[4]) if len(sys.argv)>4 else 2
RANDOMSEED = config['RANDOMSEED'] if config else 102
NUM_DAY = config['NUM_DAY'] if config else 5
NUM_WEEK = config['NUM_WEEK'] if config else 4
client_file = config['client_file'] if config else 'trace/fedscale_clients_7000000_3_info.csv'
eligibility_file = config['eligibility_file'] if config else 'trace/baseline_eligibility_3skew'

random.seed(RANDOMSEED)
np.random.seed(RANDOMSEED)

apple_job = ['AppleJob', 'DecAppleJob']
google_job = ['Job', 'AgnosticJob', 'GoogleJob', 'DecentralizedJob', 'VennGoogleJob']
async_job = ['PapayaJob', 'DecPapayaJob', 'VennPapayaJob']
venn_job_name = ['VennGoogleJob', 'VennAppleJob', 'VennPapayaJob' ]

def load_device_capacity(file_path = 'trace/client_device_capacity'):
    global_client_profile = {}
    if os.path.exists(file_path):
        with open(file_path, 'rb') as fin:
            # {clientId: [computer, bandwidth]}
            global_client_profile = pickle.load(fin)
    return global_client_profile

def load_device_eligibility(eligibility_file):
    with open(eligibility_file, 'rb') as config_dictionary_file:
        eligibility = pickle.load(config_dictionary_file)
    return eligibility

def load_device_state(client_file, eligibility_file, client_type , days  ):
    client_capacity = load_device_capacity()
    client_eligibility = load_device_eligibility(eligibility_file)
    num_cap = len(client_capacity)
    num_eli = len(client_eligibility)
    avg_comp = 78
    avg_comm = 13736
    weeks = NUM_WEEK
    client_event_list= []
    client_trace = pd.read_csv(client_file)

    client_type = eval(client_type)
    print(f"Using {client_type}")

    for i, (ind, client) in enumerate(client_trace.sort_values(by=['start']).iterrows()):
        # for i, (ind, client) in enumerate(client_trace.iterrows() ):
        if client['start'] > days * 86400:
            break

        # if client['start'] < 120: # or client['end'] - client['start'] < 20:
        #     continue

        comm = client_capacity[i % num_cap + 1]['communication'] / avg_comm
        comp = client_capacity[i % num_cap + 1]['computation'] / avg_comp
        # c = client_type(i, client['start'], client['end'], comp, comm, client_eligibility[i%num_eli])
        # client_event_list.append( Event(client['start'], 'CHECKIN', i, c)  )
        for j in range(weeks):
            # TODO: client online period is too short; remove some short-lived clients
            #  while manually increase their online period to ensure enough traffic
            start = client['start'] + j * 432000
            c = client_type( i*weeks+j, start, client['end'] + 80 + j * 432000, comp, comm, client_eligibility[i % num_eli])
            client_event_list.append(Event(start, 'CHECKIN', i*weeks+j, c))
            # c = client_type( -i*weeks+j, client['start'] + j * 432000, client['end'] + 80 + j * 432000, comp, comm, client_eligibility[i % num_eli])
            # client_event_list.append(Event(client['start'] + j * 432000, 'CHECKIN', -i*weeks+j, c))

        # if i > 10000 :
        #     break
        if i % 100000 == 0:
            print(f'Checkin {i*weeks} clients')
    return client_event_list

arrival_interval = 1800
start_time = 3600
job_start_list = [start_time]  # [0 for _ in range(num_job)]
job_minresponse_list = [0.8 for _ in range(num_job)]
comm_time = 10
timeout_list = [0 for _ in range(num_job)] #
job_workload_list = [60 for _ in range(num_job)]  # sample from 30-60?
job_deadline_list = [300 for _ in range(num_job)]  #
for i in range(num_job - 1):
    job_start_list.append(job_start_list[-1] + np.random.exponential(scale=arrival_interval))
# eligibility_list = np.random.choice([*range(0, 3)], num_job, p=[ 0.33, 0.33 , 0.34])


if not config:
    # motivation example
    # job_async_round_list =  [40000 for _ in range(num_job)] #

    buffer_size_list = [10 for _ in range(num_job) ]#
    concurrency_list = [100 for _ in range(num_job) ]#

    job_round_list = [2000 for _ in range(num_job)] #
    job_request_amount_list = [200 for _ in range(num_job)]#

    # job_workload_list =  np.random.choice(range(30, 61, 10), num_job) # [45 for _ in range(num_job)] #
    # job_round_list = np.random.choice(range(5000, 10001, 1000), num_job)
    #
    # buffer_size_list = np.random.choice(range(10, 31, 5), num_job)  # [20 for _ in range(num_job) ]#
    # concurrency_list = np.random.choice(range(50, 301, 50), num_job)  # [100 for _ in range(num_job)  ]#
    # timeout_list = job_workload_list + np.random.choice(range(60, 91, 10), num_job)
    #
    # job_round_list = np.random.choice(range(500, 1001, 100), num_job)
    # job_request_amount_list = np.random.choice(range(100, 301, 100), num_job)  # [300 for _ in range(num_job)]#
    # job_deadline_list = np.random.choice(range(600, 901, 50), num_job)  # [300 for _ in range(num_job)] #

def generate_job_by_config(num_job, job_type):
    with open('config/job_config.yml', "r") as configfile:
        job_config = yaml.load(configfile, Loader=yaml.FullLoader)

    job_deadline_list = [0 for _ in range(num_job)]  #
    request_list = []
    job_list = []
    job_request_list = []

    jobs = job_config['jobs']
    job_id_prob = np.array( config['job_id_prob'])
    job_type_prob = config['job_type_prob']
    job_id_prob =job_id_prob/ sum (job_id_prob)
    generate_jobid_by_prob = np.random.choice([*range(len(jobs))], num_job, p = job_id_prob )
    print("Random generate job id: ", generate_jobid_by_prob)
    jtype = job_type
    if jtype in async_job:
        job_deadline_list = timeout_list

    for i, job_id in enumerate(generate_jobid_by_prob):
        print(jobs[job_id])
        if job_type == 'MixedJob':
            if jobs[job_id]['config']['job_type'] == 'sync':
                jtype = np.random.choice(venn_job_name[:2], 1, p = job_type_prob[:2] )[0]
            else:
                jtype = 'VennPapayaJob'

        num_part = jobs[job_id]['config']['participants']
        if jtype in google_job:
            job_deadline_list[i] = jobs[job_id]['config']['deadline']
                # max(min(num_part * 3, 900), 300)

        job_request_list += [Request(job_deadline_list[i], num_part,
                                     job_minresponse_list[i], job_workload_list[i], comm_time,
                                     jobs[job_id]['config']['eligibility'] )]

        job_list += [eval(jtype)(i, jtype, job_request_list[i], jobs[job_id]['config']['rounds'],
                                               job_start_list[i], jobs[job_id]['config']['concurrency'])]
        # concurrency only for async --> is actually buffer size

    for job in job_list:
        request_list += job.generate_round_event()
    request_list += [Event(NUM_DAY * 86400 * NUM_WEEK, 'END', None, None)]

    return request_list, job_list, job_request_list

def generate_mixed_job_request(num_job, days):
    weeks = NUM_WEEK
    request_list = []

    job_list = []
    job_request_list = []
    job_type_list = np.random.choice(venn_job_name, num_job)
    for i, job_type in enumerate(job_type_list):
        if job_type in async_job:
            job_request_list += [Request(timeout_list[i], concurrency_list[i],
                                        job_minresponse_list[i], job_workload_list[i], comm_time,
                                        i % 3)]

            job_list += [eval(job_type)(i, job_type, job_request_list[i], job_round_list[i],
                                       job_start_list[i], buffer_size_list[i])]

        else:
            job_request_list += [Request(job_deadline_list[i], job_request_amount_list[i],
                                        job_minresponse_list[i], job_workload_list[i], comm_time,
                                        i%3 )]
            job_list += [eval(job_type)(i, job_type, job_request_list[i], job_round_list[i],
                                    start=job_start_list[i])]

    for job in job_list:
        request_list += job.generate_round_event()
    request_list += [Event(days * 86400 * weeks, 'END', None, None)]

    return request_list, job_list, job_request_list

def generate_job_request(num_job, job_type , days = 5):
    if job_type == 'RandomJob':
        return generate_mixed_job_request(num_job, days)
    if config: # MixedJob / config
        return generate_job_by_config(num_job, job_type)

    weeks = NUM_WEEK
    request_list = []
    # job_start_list = sorted(np.random.poisson(lam=days/4*10, size=num_job) * 8640)
    job_start_list = [start_time] # [0 for _ in range(num_job)]
    for i in range(num_job-1):
        job_start_list.append( job_start_list[-1] +  np.random.exponential(scale=arrival_interval) )

    if job_type in async_job:
        job_request_list = [Request(timeout_list[i], concurrency_list[i],
                                    job_minresponse_list[i], job_workload_list[i], comm_time,
                                    i%3 ) for i in range(num_job)]

        job_list = [eval(job_type)(i, job_type, job_request_list[i], job_round_list[i],
                                job_start_list[i], buffer_size_list[i]) for i in range(num_job)]

    else:
        job_request_list = [Request(job_deadline_list[i], job_request_amount_list[i],
                                    job_minresponse_list[i], job_workload_list[i], comm_time,
                                    i%3 ) for i in range(num_job)]
        job_list = [eval(job_type)(i, job_type, job_request_list[i], job_round_list[i],
                                start=job_start_list[i]) for i in range(num_job)]

    for job in job_list:
        request_list += job.generate_round_event()
    request_list += [Event(days * 86400 * weeks, 'END', None, None)]

    return request_list, job_list, job_request_list




