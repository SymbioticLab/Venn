# import re

# def extract_utilize_time(log_file_path_list):
#     utilize_times = []
#     pattern = r"utilize_time\/total_time: (\d+\.\d+)"
    
#     for log_file_path in log_file_path_list:
#         with open(log_file_path, 'r') as file:
#             for line in file:
#                 match = re.search(pattern, line)
#                 if match:
#                     utilize_time = float(match.group(1))
#                     print(utilize_time)
#                     utilize_times.append(utilize_time)

#     avg = sum(utilize_times) / len(utilize_times)
#     return avg
        

# log_file_path_list = [
#     "./experiment/job_5_client_1500_random/client/print_0.log",
#     "./experiment/job_5_client_1500_random/client/print_1.log",
#     "./experiment/job_5_client_1500_random/client/print_2.log",
# ]

# total_time = 19093.5396

# avg_utilize_time = extract_utilize_time(log_file_path_list)
# print("AVG Utilize Time:", avg_utilize_time)
# print("Utilization Rate: ", avg_utilize_time / total_time)

import csv

total_time = 15075.212
csv_file_path = './experiment/job_5_client_1800_srsf_propius/client/client_result.csv'
utilize_times = []

# Open the CSV file for reading
with open(csv_file_path, newline='') as csvfile:
    # Create a CSV reader object
    csvreader = csv.reader(csvfile)

    # Read each row in the CSV file
    for row in csvreader:
        # Each row is a list of strings; convert them to integers
        utilize_time = float(row[0])
        if utilize_time == 0: 
            continue
        print(utilize_time)
        utilize_times.append(utilize_time)

avg = sum(utilize_times) / len(utilize_times)

print("AVG Utilize Time: ", avg)
print("Utilization Rate: ", avg/total_time)
