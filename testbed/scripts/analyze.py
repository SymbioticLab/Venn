import os
import csv
import yaml
import re
import matplotlib.pyplot as plt
import numpy as np

version = "15000-new"
time_cutoff = 100000
round_cutoff = 150

plot_folder = f'./evaluation_result/plot-{version}'

sched_alg_list = [
                  'random',
                  'fifo',
                  'srsf',
                #   'venn',
                  'vennm'
                  ]

# color_list_cell = ['black', 'grey', 'blueviolet', 'darkorange', 'teal']
color_list_cell = ['black', 'grey', 'blueviolet', 'teal']
# line_style = [':', '-.', '--', '-', '-']
line_style = [':', '-.', '--', '-']
plot_option = 'acc'
plt.rcParams.update({'font.size': 18})
fig, ax = plt.subplots(figsize=(5.4, 4), constrained_layout=True)
ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)

job_num = 20

if not os.path.exists(plot_folder):
    os.makedirs(plot_folder)

round_info_dict = {}

for i, sched_alg in enumerate(sched_alg_list):
    if sched_alg == 'venn':
        sched_alg = 'irs3'
    elif sched_alg == 'vennm':
        sched_alg = 'irs3m'

    round_list_dict = {}
    round_time_list_dict = {}
    acc_list_dict = {}
    avg_tloss_dict = {}
    end_time_list = []

    execute_folder = f'evaluation_result/{sched_alg}-{version}/executor'
    job_folder = f'evaluation_result/{sched_alg}-{version}/job'

    file_sched = sched_alg
    if sched_alg == 'irs3m':
        file_sched = 'irs3'

    pattern = re.compile(f"test_(\d+)\_{file_sched}.csv")

    for exe_res_name in os.listdir(execute_folder):
        match = re.search(pattern, exe_res_name)
        if match:
            exe_res_file_path = os.path.join(execute_folder, exe_res_name)
            job_id = match.group(1)

            ps_result_file_name = f"job_{job_id}_{file_sched}.csv"
            ps_result_file_path = os.path.join(job_folder, ps_result_file_name)

            time_stamp_list = [0]
            acc_list = []
            acc_5_list = []
            round_list = []
            avg_tloss_list = []

            with open(exe_res_file_path, "r") as exe_file:
                reader = csv.reader(exe_file)
                header = next(reader)
                acc_idx = header.index("acc")
                acc_5_idx = header.index("acc_5")
                round_idx = header.index("round")
                avg_loss_idx = header.index("test_loss")
                for row in reader:
                    round = int(row[round_idx])
                    round_list.append(round)
                    acc_list.append(float(row[acc_idx]))
                    avg_tloss_list.append(float(row[avg_loss_idx]))
                    if round == round_cutoff:
                        break

            round_num = 0
            with open(ps_result_file_path, "r") as ps_file:
                reader = csv.reader(ps_file)
                header = next(reader)

                idx = header.index("round_time")
                round_idx = header.index("round")
                for row in reader:
                    round_num = int(row[round_idx])
                    round_time = float(row[idx])
                    if round_time > time_cutoff:
                        break
                    if round_num in round_list:
                        time_stamp_list.append(round_time)
                    if round_num == round_cutoff:
                        break

            acc_list = acc_list[0:len(time_stamp_list)]
            avg_tloss_list = avg_tloss_list[0:len(time_stamp_list)]
            job_id = int(job_id) % 100

            # round_list_dict[job_id] = round_list
            round_info_dict[f"{job_id}-{sched_alg}"] = time_stamp_list[-1]

            if time_stamp_list[-1] > time_cutoff:
                continue
            end_time_list.append(time_stamp_list[-1])

            round_time_list_dict[job_id] = time_stamp_list
            acc_list_dict[job_id] = acc_list
            avg_tloss_dict[job_id] = avg_tloss_list

    avg_end_time = sum(end_time_list) / len(end_time_list)
    end_time = max(end_time_list)
    round_info_dict[f"avg-{sched_alg}"] = (avg_end_time, end_time)

    mean_x_axis = [i for i in range(int(avg_end_time))]
    ys_interp = []
    for j in round_time_list_dict.keys():

        if plot_option == 'acc':
            ys_interp.append(np.interp(mean_x_axis, round_time_list_dict[j], acc_list_dict[j]))
        elif plot_option == 'test_loss':
            ys_interp.append(np.interp(mean_x_axis, round_time_list_dict[j], avg_tloss_dict[j]))

    mean_y_axis = np.mean(ys_interp, axis=0)

    if sched_alg == 'irs3':
        alg_label = 'Venn w/o match'
    elif sched_alg == 'irs3m':
        alg_label = 'Venn'
    elif sched_alg == 'fifo':
        alg_label = 'FIFO'
    elif sched_alg == 'random':
        alg_label = 'Random'
    elif sched_alg == 'srsf':
        alg_label = 'SRSF'
    plt.plot(mean_x_axis, mean_y_axis, label=f"{alg_label}", color=color_list_cell[i], linestyle=line_style[i], linewidth=3)

plt.xlabel('Time (seconds)')

if plot_option == 'acc':
    plt.ylabel('Avg. Test Accuracy')
elif plot_option == 'test_loss':
    plt.ylabel("Avg. Test Loss")
# plt.title(f'Average Job Time to Accuracy Plot under Various Scheduling Policies, FEMNIST, {version}')
plt.ylim([0.6, 0.75])
plt.xlim([4000, 26000])
plt.grid(axis='y', linestyle='--', alpha=0.7)
plt.xticks(  [*range(5000,30000, 10000)], [*range(5000,30000, 10000)])
plt.yticks( rotation=90)
plt.legend()
plt.xlabel('Time (s)')
plt.rcParams['font.family'] = 'Arial'

# output_plot_name = f'tta-acc-no-irs.png'
output_plot_name = f"{plot_option}-{version}.pdf"
output_plot_path = os.path.join(plot_folder, output_plot_name)
plt.savefig(output_plot_path)

output_file_name = f'round.txt'
output_file_path = os.path.join(plot_folder, output_file_name)
with open(output_file_path, "w") as file:
    for key, value in round_info_dict.items():
        file.write(f"{key} - {value}\n")
        





