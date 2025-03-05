
import yaml
from job import *
import pandas as pd
import numpy as np
import os, pickle
from util import Event, Request
from client import *
from venn import *
from venn_job import *
from venn_client import *


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
if str(sys.argv[1]).startswith("Random") or str(sys.argv[1]).startswith("LAS"):
    NUM_WEEK *= 2
# elif not str(sys.argv[1]).startswith("AMG"):
#     NUM_WEEK += 10
print("NUM_WEEK: ", NUM_WEEK)
client_file = config['client_file'] if config else 'trace/fedscale_clients_7000000_3_info.csv'
eligibility_file = config['eligibility_file'] if config else 'trace/baseline_eligibility_3skew'
job_config_file = config['job_config_file'] if 'job_config_file' in config else 'config/job_config.yml'


random.seed(RANDOMSEED)
np.random.seed(RANDOMSEED)

apple_job = ['AppleJob', 'DecAppleJob']
google_job = ['Job', 'AgnosticJob', 'GoogleJob', 'DecentralizedJob', 'GoogleJob']
async_job = ['PapayaJob', 'DecPapayaJob', 'PapayaJob']
amg_job_name = ['GoogleJob', 'AppleJob', 'PapayaJob' ]

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


job_minresponse_list = [0.8 for _ in range(num_job)]
comm_time = 10

def generate_job_by_config(num_job, job_type):
    with open(job_config_file, "r") as configfile:
        job_config = yaml.load(configfile, Loader=yaml.FullLoader)

    job_deadline_list = [0 for _ in range(num_job)]  #
    request_list = []
    job_list = []
    job_request_list = []
    if 'arrival_interval' in job_config:
        arrival_interval = job_config['arrival_interval']
    else:
        arrival_interval = 1800
    start_time = 3600
    job_start_list = [start_time]
    for i in range(num_job - 1):
        job_start_list.append(job_start_list[-1] + np.random.exponential(scale=arrival_interval))

    num_job_req = len(job_config['job_requirement'])
    jobs = job_config['jobs']
    job_id_prob = np.array( config['job_id_prob'])
    job_type_prob = config['job_type_prob']
    job_id_prob = job_id_prob/ sum (job_id_prob)
    generate_jobid_by_prob = np.random.choice([*range(len(jobs))], num_job, p = job_id_prob )
    print("Random generate job id: ", generate_jobid_by_prob)
    jtype = job_type
    if jtype in async_job:
        job_deadline_list = [0 for _ in range(num_job)] #

    for i, job_id in enumerate(generate_jobid_by_prob):
        print(jobs[job_id])
        if job_type == 'MixedJob':
            if jobs[job_id]['config']['job_type'] == 'sync':
                jtype = np.random.choice(amg_job_name[:2], 1, p = job_type_prob[:2] )[0]
            else:
                jtype = 'PapayaJob'

        num_part = jobs[job_id]['config']['participants']
        if jtype in google_job:
            job_deadline_list[i] = jobs[job_id]['config']['deadline']
        job_workload = jobs[job_id]['config']['workload']
        eligibility = jobs[job_id]['config']['eligibility'] if 'eligibility' in jobs[job_id]['config'] else i%num_job_req
        job_request_list += [Request(job_deadline_list[i], num_part,
                                     job_minresponse_list[i], job_workload, comm_time,
                                     eligibility)]

        job_list += [eval(jtype)(i, jtype, job_request_list[i], jobs[job_id]['config']['rounds'],
                                               job_start_list[i], jobs[job_id]['config']['concurrency'])]
        # concurrency only for async --> is actually buffer size

    for job in job_list:
        request_list += job.generate_round_event()
    request_list += [Event(NUM_DAY * 86400 * NUM_WEEK, 'END', None, None)]

    return request_list, job_list, job_request_list


def generate_job_request(num_job, job_type , days = 5):
    if config: # MixedJob / config
        return generate_job_by_config(num_job, job_type)


