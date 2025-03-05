# Propius
Propius is a collaborative machine learning (or federated learning) resource manager, capable of efficiently scheduling devices in a multi-job setting.

## Repository Organization
```
.
├── propius_controller/             # Propius Python package
│   ├── client_manager/             #   - Edge device (client) interface
│   ├── job_manager/                #   - FL job interface
│   ├── load_balancer/              #   - Distributor of client traffics to client managers
│   ├── scheduler/                  #   - FL job scheduler, capable of executing various policies
│   ├── util/                       #   - Utility functions and classes
│   ├── channels/                   #   - gRPC channel source code and definitions
│   ├── database/                   #   - Redis database base interface
│   ├── propius_job/                #   - Propius job interface library
│   │   └── propius_job.py          #       - Class for Propius-job interface
│   ├── propius_client/             #   - Propius client interface library
│   │   ├── propius_client.py       #       - Class for Propius-client interface
│   │   └── propius_client_aio.py   #       - asyncio-based class for Propius-client interface
│   └── global_config.yml           #   - Configuration for Propius system
│
├── evaluation/                     # Framework for evaluating scheduling policies
│   ├── executor/                   #   - Executor for FL training and testing tasks using multiple GPU processes
│   ├── client/                     #   - Dispatcher of simulated clients
│   ├── job/                        #   - Dispatcher of simulated jobs
│   └── evaluation_config.yml       #   - Configuration for evaluation
│
├── docs/                           # Documentation
│
├── scripts/                        # Helpful scripts that make lives easier
│
├── tests/                          # Test suites
│ 
├── examples/                       # Examples of integrating Propius
│ 
└── datasets/                       # FL datasets and client device traces
```

## Getting Started
- [Install packages in a virtual environment using pip and venv](https://packaging.python.org/en/latest/guides/installing-using-pip-and-virtual-environments/)
    - Preferred, light-weight solution
    - Use `python -m pip install .` once the env is activated
    - `python -m pip install -r requirements.txt`
- Quick installation (Linux / MacOS) with Anaconda/miniconda
```bash
source install.sh # add `--cuda` if you want CUDA
pip install -e .
```
- [Step-by-step installation](./docs/getting_started/getting_started.md) with Anaconda/miniconda
## Usage
### Quick Launch
We use docker compose to containerize components (job manager, scheduler, client manager, load balancer and Redis DB) in a docker network.
- Run:
```bash
chmod +x propius/controller/client_manager/entrypoint.sh
```
- Based on whether running ML workloads on GPU is conducted or not, edit and run `config.py` script for configuring docker compose files and Propius config file. You can choose from `PROPIUS_SYS` (just running the Propius system) and `PROPIUS_EVAL` (running system + generating client loads + run workloads on GPU). Set `propius_use_docker = False`.
```bash
python config.py
```
    <!-- - Alternatively:
        - Edit `compose_propius.yml` and `propius/global_config.yml`. By default, the network address of load balancer (client interface) is `localhost:50002`, and the address of job manager (job interface) is `localhost:50001`
        - Make sure the setup is consistent across two config files
        - By default, Propius has two client managers and two client databases. For handling large amount of clients, we support horizontal scaling of client manager and client database. To achieve this, you need to add more client manager and database services in `compose_propius.yml`, and edit `propius/global_config.yml` accordingly -->
- Run docker compose
```bash
docker compose -f compose_propius.yml up --build # -d if want to run Propius in background
```
- Monitoring
```bash
chmod +x ./scripts/monitor_propius.sh
./scripts/monitor_propius.sh
```
- Shut down
```bash
docker compose -f compose_propius.yml down
```
### Manual Lanuch
Propius can be started without docker. However, for the ease of deployment, the Redis database is containerized.
- Edit `config.py` file, set `propius_use_docker = False` and run
<!-- - Edit `propius/global_config.yml` and `compose_redis.yml`. Make sure these two files are consistent -->
- Launch Redis Database in background
```bash
docker compose -f compose_redis.yml up -d
```
- Launch major components in Propius. You can use tools such as [tmux](https://github.com/tmux/tmux/wiki) to organize your terminal.
    - Scheduler:
    ```bash
    propius-controller-scheduler
    ```
    - Job manager:
    ```bash
    propius-controller-job-manager
    ```
    - Client manager:
    ```bash
    propius-controller-client-manager 0 # <id>
    propius-controller-client-manager 1 # <id>
    ```
    - Load balancer:
    ```bash
    propius-controller-load-balancer
    ```
- By default, Propius has two client managers and two client databases. For handling large amount of clients, we support horizontal scaling of client manager and client database. To achieve this, you need to add more client manager and database services `propius/global_config.yml` and `compose_redis.yml`. Make sure the setting is consistent. You also need to start the additional client manager services manually.
- Monitoring
```bash
chmod +x ./scripts/monitor_propius.sh
./scripts/monitor_propius.sh
```
- Shut down
```bash
docker compose -f compose_redis.yml down
# ctrl-c on every process you launch 
```

## Interface
- Propius' job interface is defined in `propius/controller/job/propius_job.py`
- Propius' client interface is defined in `propius/controller/client/propius_client.py`
- Refer to `examples/` to get an idea how your FL job and FL client can utilize Propius

## Evaluation
For the ease of evaluation, we containerize Propius and essential peripherals for evaluation in one docker network using docker compose. You should change `compose_eval_gpu.yml` file based on the number of available GPU servers.
- Download Dataset
```bash
source ./datasets/download.sh
```
- Create or edit job profile in `evaluation/job/profile/`
- Edit and run configuration script
```bash
python config.py
```
- Start docker network
```bash
chmod +x evaluation/executor/entrypoint.sh
chmod +x propius/client_manager/entrypoint.sh
chmod +x evaluation/job/entrypoint.sh
chmod +x evaluation/client/entrypoint.sh
docker compose -f compose_eval_gpu.yml up --build -d
```
- Monitoring
```bash
chmod +x ./scripts/monitor_propius.sh
./scripts/monitor_propius.sh

chmod +x ./scripts/monitor_eval.sh
./scripts/monitor_eval.sh

chmod +x ./scripts/monitor_jobs.sh
./scripts/monitor_jobs.sh
```
- Analyze
```bash
python ./scripts/analyze_roundtime.py # Give you insight on round time, sched latency etc.
python ./scripts/analyze.py # Make time vs accuracy, time vs loss plot
```
- Shutdown & Clean up
```bash
docker compose -f compose_eval_gpu.yml down
chmod +x ./scripts/clean.sh
./scripts/clean.sh
```

## Testing
- Edit `config.py` file, set `propius_use_docker = False` and run
```
pytest -v tests
```
## Error Handling
- If there is an error saying that you cannot connect to docker daemon, try [this](https://stackoverflow.com/questions/48957195/how-to-fix-docker-got-permission-denied-issue)
- Check Redis server is running
    - [Install redis-cli](https://stackoverflow.com/questions/21795340/linux-install-redis-cli-only)
    ```bash
    redis-cli -h localhost -p 6379 ping
    redis-cli -h localhost -p 6380 ping
    ```

## RoadMap
- Please refer to [Project](https://github.com/users/EricDinging/projects/1) page for more information



