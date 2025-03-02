

import numpy as np
import random
import pickle

def generate_eligibility(filename, job_amount, prob_list, client_amount = 500000, skew = False):
    client_list = [set() for _ in range(client_amount)]
    for j in range(job_amount):
        for i in range(client_amount):
            if random.random() > prob_list[j]:
                if skew:
                    job_type = np.random.choice([*range(1, job_amount+1 )], p=[0.5, 0.2, 0.3])
                else:
                    job_type = random.randint(1, job_amount)
                client_list[i].add(job_type)
    client_list = [list(i) for i in client_list]

    with open(filename, 'wb') as outp:  # Overwrites any existing file.
        pickle.dump(client_list, outp, pickle.HIGHEST_PROTOCOL)

    return client_list

def generate_within_eligibility(filename, job_amount, prob_list, client_amount = 500000, skew = False):
    client_list = [[] for _ in range(client_amount)]

    for i in range(client_amount):
        job_type = [1]
        if random.random() < 0.6:
            job_type.append(2)
            if random.random() < 0.5:
                job_type.append(3)
        client_list[i] = job_type
    with open(filename, 'wb') as outp:  # Overwrites any existing file.
        pickle.dump(client_list, outp, pickle.HIGHEST_PROTOCOL)

    return client_list

def generate_cross_eligibility(filename, job_amount, prob_list, client_amount = 500000, skew = False):
    client_list = [[] for _ in range(client_amount)]

    for i in range(client_amount):

        count = 2 if random.random() < 0.5 else 1
        job_type =list( np.random.choice([*range(1, job_amount )], count, p=[0.2,0.8]))

        if 2 in job_type and 1 not in job_type and random.random() < 0.5:
            job_type.append(job_amount)

        client_list[i] = job_type


    with open(filename, 'wb') as outp:  # Overwrites any existing file.
        pickle.dump(client_list, outp, pickle.HIGHEST_PROTOCOL)

    return client_list



if __name__ == '__main__':
    # generate_eligibility('baseline_eligibility_3job', 3, [0, 0.5, 0.8])
    generate_cross_eligibility('baseline_eligibility_3cross', 3, [0, 0.5, 0.8],client_amount = 50000, skew = True)
    # generate_within_eligibility('baseline_eligibility_3_within', 3, [0, 0, 0],client_amount = 50000, skew = True)



a=b=c=d=f=g=h=0
eligibility_file = 'baseline_eligibility_3cross'
with open(eligibility_file, 'rb') as config_dictionary_file:
    eligibility = pickle.load(config_dictionary_file)
for e in eligibility:
    if 1 in e:
        a += 1
    if 2 in e:
        b+=1
    if 3 in e:
        c += 1
    if 1 in e and 2 in e:
        d += 1
    if 1 in e and 3 in e:
        f += 1
    if 3 in e and 2 in e:
        g += 1
    if 1 in e and 2 in e and 3 in e:
        h += 1
