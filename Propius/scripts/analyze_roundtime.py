"""A python script that performs analysis on JCT, scheduling latency and
response time across all simulated jobs
"""

import os
import csv

sched_alg = "irs3m"
folder_path = f"./evaluation_result/{sched_alg}-15000-new/job/"

analyze_certain_rounds = False

print(folder_path)

if not os.path.exists(folder_path):
    raise FileNotFoundError("The specified folder does not exist.")


def read_last_line(csv_file):
    with open(csv_file, "r", newline="") as file:
        csv_reader = csv.reader(file)
        round_time = 0
        sched_time = 0
        resp_time = 0
        last_row = None
        total_round = 0
        sched_timeout = 0
        resp_timeout = 0
        for row in csv_reader:
            if row[0] == "-1":
                print(row)
                round_time = float(last_row[1])
                sched_time = float(row[2])
                resp_time = float(row[3])
            elif row[0] == "-2":
                print(row)
                sched_timeout += int(row[2])
                resp_timeout += int(row[3])
                break
            else:
                total_round += 1
            last_row = row

        total_sched_time = sched_time * round_time / (sched_time + resp_time)
        total_resp_time = resp_time * round_time / (sched_time + resp_time)

        return (
            round_time,
            sched_time,
            resp_time,
            total_round,
            total_sched_time,
            total_resp_time,
            sched_timeout,
            resp_timeout,
        )


def read_first(round, csv_file):
    with open(csv_file, "r", newline="") as file:
        csv_reader = csv.reader(file)
        time_round = 0
        sched_time = 0
        resp_time = 0
        num = 0
        for row in csv_reader:
            if row[0] == "round":
                continue
            sched_time += float(row[2])
            resp_time += float(row[3])
            num += 1
            if num == round:
                time_round = float(row[1])
                break

        sched_time /= num if num > 0 else 1
        resp_time /= num if num > 0 else 1

        return (time_round, sched_time, resp_time)


if analyze_certain_rounds:
    round = int(input("round: "))
    for filename in os.listdir(folder_path):
        if filename.endswith(".csv"):
            csv_file_path = os.path.join(folder_path, filename)
            round_time, sched, response = read_first(round, csv_file_path)
            print(
                f"{filename}, round: {round} time: {round_time}, avg sched: {sched}, avg_response: {response}"
            )
else:
    upper_round = upper_sched = upper_resp = 0
    total_round = total_sched = total_resp = 0
    lower_round = lower_sched = lower_resp = 1000000000
    num = 0

    job_info_map = {}

    sum_total_job_round = 0
    sum_total_job_sched = 0
    sum_total_job_response = 0

    total_sched_timeout = 0
    total_resp_timeout = 0

    for filename in os.listdir(folder_path):
        if filename.endswith(".csv"):
            csv_file_path = os.path.join(folder_path, filename)
            # if csv_file_path in ['./evaluation_result/irs3-6000-new/job/job_60000_irs3.csv', './evaluation_result/fifo-6000-new/job/job_60000_fifo.csv']:
            #     continue

            print(filename)
            (
                round_time,
                sched,
                response,
                total_job_round,
                total_job_sched,
                total_job_response,
                sched_timeout,
                resp_timeout
            ) = read_last_line(csv_file_path)
            print("")

            job_info_map[filename] = (round_time, sched, response)

            num += 1
            total_round += round_time
            total_sched += sched
            total_resp += response

            sum_total_job_round += total_job_round
            sum_total_job_sched += total_job_sched
            sum_total_job_response += total_job_response

            upper_round = round_time if round_time > upper_round else upper_round
            lower_round = round_time if round_time < lower_round else lower_round
            upper_sched = sched if sched > upper_sched else upper_sched
            lower_sched = sched if sched < lower_sched else lower_sched
            upper_resp = response if response > upper_resp else upper_resp
            lower_resp = response if response < lower_resp else lower_resp

            total_sched_timeout += sched_timeout
            total_resp_timeout += resp_timeout

    avg_round = total_round / num
    avg_sched = total_sched / num
    avg_response = total_resp / num

    weighted_avg_rct = (
        sum_total_job_response + sum_total_job_sched
    ) / sum_total_job_round

    print(
        f"Avg finish time: {avg_round:.3f}, avg queueing delay: {avg_sched:.3f}, avg response time: {avg_response:.3f}"
    )
    print(
        f"Avg RCT: {avg_sched + avg_response:.3f}, Weighted Avg RCT: {weighted_avg_rct:.3f}"
    )
    print(f"Upper finish time: {upper_round:.3f}, Lower finish time: {lower_round:.3f}")
    print(
        f"Upper queueing time: {upper_sched:.3f}, Lower queueing time: {lower_sched:.3f}"
    )
    print(
        f"Upper response time: {upper_resp:.3f}, Lower response time: {lower_resp:.3f}"
    )

    print(f"sched timeout: {total_sched_timeout}, resp timeout: {total_resp_timeout}")

    job_info_map = dict(sorted(job_info_map.items()))
    print("File: end time, avg sched latency, avg response collection latency")
    for key, val in job_info_map.items():
        print(f"{key}: {val}")
