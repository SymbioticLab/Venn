import yaml
import random
import numpy as np

random.seed(42)

# generate txt with format: time in minute, profile num, job_id
if __name__ == '__main__':
    global_setup_file = './evaluation/evaluation_config.yml'
    with open(global_setup_file, "r") as gyamlfile:
        gconfig = yaml.load(gyamlfile, Loader=yaml.FullLoader)
        total_job = gconfig['total_job']

        avg_interval = 60 * 30
        time_intervals = np.random.exponential(
            scale=avg_interval, size=total_job - 1)

        job_profile_num = total_job
        job_list = list(range(total_job))
        random.shuffle(job_list)

        with open(f"./evaluation/job/trace/job_trace_{total_job}.txt", "w") as file:
            time = 0
            job_id = 0
            file.write(f'0 {job_list[0]}\n')
            idx = 1
            for i in time_intervals:
                time += i
                file.write(f'{int(i)} {job_list[idx]}\n')
                idx += 1