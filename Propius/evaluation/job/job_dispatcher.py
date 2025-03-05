import subprocess
import yaml
import time
import os
import sys

start_row = int(sys.argv[1])
end_row = int(sys.argv[2])
driver_id = int(sys.argv[3])

with open('./evaluation/evaluation_config.yml', 'r') as gyamlfile:
    config = yaml.load(gyamlfile, Loader=yaml.FullLoader)
    ip = config['job_driver_ip'] if not config["dispatcher_use_docker"] else f"jobs_{driver_id}"
    port = int(config['job_driver_starting_port'])
    # num = config['total_job']
    trace_file = config['job_trace']

    with open(trace_file, "r") as file:
        i = 0
        time.sleep(10)

        job_processes = []
        for line in file:
            if i >= end_row:
                break
            line = line.strip().split(" ")
            sleeping_time = int(line[0]) / config['speedup_factor']
            time.sleep(sleeping_time)

            if i < start_row:
                i += 1
                continue
            
            command = [
                "python",
                "./evaluation/job/parameter_server.py",
                os.path.join(config['profile_folder'], f"job_{line[1]}.yml"),
                f"{ip}",
                f"{port + i}"]
            print(command)
            if config["dispatcher_use_docker"]:
                p = subprocess.Popen(command, shell=False, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            else:
                p = subprocess.Popen(command)
            job_processes.append(p)
            i += 1

        for p in job_processes:
            p.wait()