
import pandas as pd
import numpy as np
import random
# from plot import plot_utilization
import matplotlib.pyplot as plt

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


def generate_eligibility(client_amount, job_amount, prob_list, skew = False):
    client_list = [set() for _ in range(client_amount)]
    for j in range(job_amount):
        for i in range(client_amount):
            if random.random() > prob_list[j]:
                if skew:
                    job_type = np.random.choice([*range(1, job_amount+1 )], p=[0.1, 0.45, 0.45])
                else:
                    job_type = random.randint(1, job_amount)
                client_list[i].add(job_type)
    client_list = [list(i) for i in client_list]
    return client_list


def generate_clients(client_amount, job_amount, prob_list = None):
    if prob_list is None:
        prob_list = np.linspace(0, 0.7, num=job_amount)


    client_id = [*range(client_amount)]
    job_list = generate_eligibility(client_amount, job_amount, prob_list)

    checkin_list =  np.clip( np.random.normal(43200, 20000, client_amount),0, 86400)
    duration = np.random.poisson(5, client_amount)*144
    end_list = checkin_list + duration
    plot_availability(list(checkin_list), list(end_list))
    data = { 'ID': client_id,
             'start': list(checkin_list),
             'end': list(end_list),
             'type': job_list}
    df = pd.DataFrame(data )
    # print(df)
    filepath = f'clients_{client_amount}_{job_amount}_info.csv'
    print(f"Write client info to {filepath}")
    df.to_csv(filepath)

def plot_availability(checkin_list, end_list):
    # np.concatenate((checkin_list, end_list.T), axis=1)
    client_len = len(checkin_list)
    intervals = []
    for i in range(client_len):
        intervals.append([int(checkin_list[i]), int(end_list[i])])

    plot_utilization(intervals)

def main(client_file):
    client_trace = pd.read_csv(client_file)

    plt.hist(np.array(list(client_trace['end']))-np.array(list(client_trace['start'])), bins = range(0,1000))
    # plt.hist(list(client_trace['start']), bins = 100)
    plt.show( )
    # plot_availability(client_trace['start'], client_trace['end'])


def read_fedscale(client_amount, job_amount, prob_list = None, skew=False):
    if prob_list is None:
        prob_list = np.linspace(0, 0.7, num=job_amount)
    import pickle
    device_avail_file = 'client_behave_trace'

    with open(device_avail_file, 'rb') as fin:
        user_trace = pickle.load(fin)
    user_trace_keys = list(user_trace.keys())

    # job_list = generate_eligibility(client_amount, job_amount, prob_list, skew)

    checkin_list =  []
    end_list =  []

    for i,k in enumerate(user_trace_keys):
        start, end = user_trace[k]['active'], user_trace[k]['inactive']
        checkin_list+=start
        end_list+=end
        # if len(end_list) > client_amount:
        #     break

    # plot_availability(list(checkin_list), list(end_list))
    client_id = [*range(len(end_list))]
    # end_list = end_list[:client_amount]
    # checkin_list = checkin_list[:client_amount]
    data = { 'ID': client_id,
             'start': list(checkin_list),
             'end': list(end_list),
             # 'type': job_list
             }
    df = pd.DataFrame(data )
    # print(df)
    filepath = f'fedscale_clients_{client_amount}_{job_amount}_info.csv'
    print(f"Write client info to {filepath}")
    df.to_csv(filepath)



if __name__ == '__main__':
    # generate_clients(100000, 3, [0, 0.5, 0.8] )
    # read_fedscale(7000000, 3, [0, 0.5, 0.8], False )
    main('fedscale_clients_7000000_3_info.csv')