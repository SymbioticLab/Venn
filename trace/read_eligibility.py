import pandas as pd
import yaml
import pickle
import os
import random


def load_or_fetch_data(device_config):
    if os.path.exists(device_config):
        with open(device_config, 'rb') as fin:
            score_table = pickle.load(fin)
    else:
        url1 = 'https://ai-benchmark.com/ranking.html'
        score_table = pd.read_html(url1)[1]
        score_table = score_table.drop([0], axis=0)
        with open(device_config, 'wb') as outp:
            pickle.dump(score_table, outp, pickle.HIGHEST_PROTOCOL)
    return score_table


def convert_to_int(s):
    s = s.split('.')[0]
    s = ''.join(filter(str.isdigit, s))
    return int(s)


def load_job_requirements(job_requirement_file):
    with open(job_requirement_file, "r") as configfile:
        job_config = yaml.load(configfile, Loader=yaml.FullLoader)
    return job_config['job_requirement']


def is_device_eligible(device_trace, job_requirements):
    return all(device_trace[prop] >= job_requirements[prop] for prop in job_requirements)


def assign_job_types_to_clients(score_table, job_requirements, filename):
    cpu_scores = list(score_table['CPU-F Score'])
    mem_scores = list(score_table['FP16 Memory'])
    # model_names = list(score_table['Model'])
    os_versions = list(score_table['Android'])

    # Convert OS versions to integers
    clean_os_versions = [convert_to_int(s) for s in os_versions]

    num_req = len(job_requirements)
    client_amount = len(cpu_scores)
    client_list = [[] for _ in range(client_amount)]

    for i in range(client_amount):
        job_types = []
        device_trace = {
            'cpu': cpu_scores[i],
            'memory': mem_scores[i],
            'os': clean_os_versions[i]
        }
        for j in range(num_req):
            if is_device_eligible(device_trace, job_requirements[j]['eligibility']):
                job_types.append(j + 1)
        client_list[i] = job_types

    random.shuffle(client_list)

    with open(filename, 'wb') as outp:
        pickle.dump(client_list, outp, pickle.HIGHEST_PROTOCOL)


if __name__ == "__main__":
    device_config = 'aibenchmark_ranking'
    job_requirement_file = '../config/job_config.yml'
    filename = 'aibenchmark_eligibility_4'

    score_table = load_or_fetch_data(device_config)
    job_requirements = load_job_requirements(job_requirement_file)

    assign_job_types_to_clients(score_table, job_requirements, filename)
