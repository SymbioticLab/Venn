
import pandas as pd
import numpy as np
import random

def generate_job(batch_size,request_amount, duration  ):
    # [[100, 50s], [100, 50s], [100, 50s], ...]
    request_list = [[request_amount, duration] for _ in range(batch_size)]
    return request_list

def generate_batch_job( job_amount, batch_size, interval, request_amount, duration_list  ):

    request_list = [[] for _ in range(batch_size)]
    start_time = [*range(0 , batch_size*interval, interval ) ]

    for time in range(batch_size):
        batch_job = []
        # request_list[time] = [[ ]for _ in range(job_amount)]
        # each batch: [[1, 10 cilents, 0s , 600s ], [...], [...]]
        for type in range(job_amount):

            request = request_amount[type]
            duration = duration_list[type]
            batch_job.append([type+1, request, start_time[time] , duration])
        request_list[time].append(batch_job)

    # print(request_list)
    return request_list

def plot_request( job_amount, batch_size, interval, request_amount, duration_list  ):

    import matplotlib.pyplot as plt
    # start_end_list.sort(key=lambda x: x[0])
    # request_list = [[] for _ in range(batch_size)]
    start_time = [*range(0 , batch_size*interval, interval ) ]
    start_end_list = []
    for time in range(batch_size):
        # batch_job = []
        # request_list[time] = [[ ]for _ in range(job_amount)]
        # each batch: [[1, 10 cilents, 0s , 600s ], [...], [...]]
        for type in range(job_amount):

            request = request_amount[type]
            duration = duration_list[type]
            # batch_job.append([type+1, request, start_time[time] , duration])
            start_end_list.append([  start_time[time] , start_time[time] + duration, request  ] )
        # request_list[time].append(batch_job)


    max_len = 86400
    res = [0 for _ in range(max_len)]
    for interval in start_end_list:
        start, end, num = interval[0], min(interval[1], max_len), interval[2]
        for i in range(start, end):
            res[i] += num

    plt.plot(res)
    plt.ylabel('Ideal request')
    plt.show()



if __name__ == '__main__':
    plot_request(3, 100, 800, [1500,2000,5000], [200, 400, 50])


