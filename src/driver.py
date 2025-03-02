import subprocess
import sys

config_file = str(sys.argv[1]) if len(sys.argv) > 1 else 'config/s_wl.yml'
num_job = str(sys.argv[2]) if len(sys.argv) > 2 else '50'
large_config_file = config_file.replace('_wl', '_large_wl')

commands = [
    # ['python', 'amg_event.py', 'FIFOReqScheduler', 'MixedJob', 'AMGClient', num_job, config_file, '&'],
    ['python', 'amg_event.py', 'SmallReqScheduler', 'MixedJob', 'AMGClient', num_job, large_config_file, '&'],
    ['python', 'amg_event.py', 'FIFOScheduler', 'MixedJob', 'AMGClient', num_job, config_file, '&'],
    ['python', 'amg_event.py', 'RandomOrderScheduler', 'MixedJob', 'AMGClient', num_job, config_file, '&'],
    ['python', 'amg_event.py', 'AMGMatchScheduler', 'MixedJob', 'AMGClient', num_job, config_file, '2', '&'],
    ['python', 'amg_event.py', 'AMGReqScheduler', 'MixedJob', 'AMGClient', num_job, large_config_file],
    # ['python', 'amg_event.py', 'AMGMatcher', 'MixedJob', 'AMGClient', num_job, config_file, '2', '&'],
    # ['python', 'amg_event.py', 'AMGMatchScheduler', 'MixedJob', 'AMGClient', num_job, config_file, '3', '&'],
    # ['python', 'amg_event.py', 'AMGMatcher', 'MixedJob', 'AMGClient', num_job, config_file, '3', '&'],
    ['python', 'send.py', config_file],
]
# ['python', 'amg_event.py', 'LASScheduler', 'MixedJob', 'AMGNormalClient', num_job, config_file, '&'],
# ['python', 'amg_event.py', 'AMGPeriodScheduler', 'MixedJob', 'AMGNormalClient', num_job, config_file, '&'],
# ['python', 'amg_event.py', 'SmallestScheduler', 'MixedJob', 'AMGNormalClient', num_job, config_file, '&'],

processes = []

# Run the commands in parallel
for command in commands:
    print(' '.join(command))
#     process = subprocess.Popen(command)
#     processes.append(process)
#
#
# # Wait for all processes to complete
# for process in processes:
#     process.wait()
#