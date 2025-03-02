# Venn: Resource Management Across Federated Learning Jobs

[![arXiv](https://img.shields.io/badge/arXiv-2312.08298v1-b31b1b.svg)](https://arxiv.org/abs/2312.08298v1)

Venn is a federated learning (FL) resource manager that efficiently schedules ephemeral, heterogeneous edge devices among multiple FL jobs, reducing average job completion time.

## Installation

To set up the conda environment, follow these steps:

1. Download and install Miniconda:
   ```bash
   wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -O ~/miniconda.sh
   bash ~/miniconda.sh -b -p $HOME/miniconda
   eval "$($HOME/miniconda/bin/conda shell.bash hook)"
   conda init
   source ~/.bashrc
   ```

2. Create the conda environment:
   ```bash
   conda create --name venn_env python=3.8 --yes
   conda activate venn_env
   ```

3. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/Venn.git
   cd Venn
   ```

4. Install the Venn package:
   ```bash
   pip install -e .
   ```

## Usage
Run simulations for scheduling FL jobs using the following command:
```bash
python src/venn_event.py <Scheduler> <JobType> <ClientType> <NumJobs> <ClientAndJobTrace>
```

Quick Test - Small Scale FL Jobs Scheduling:
```bash
python src/venn_event.py SmallReqScheduler MixedJob VennClient 50 config/test.yml
python src/venn_event.py FIFOScheduler MixedJob VennClient 50 config/test.yml 
python src/venn_event.py VennReqScheduler MixedJob VennClient 50 config/test.yml 
```

Commands to reproduce Table 1 line 1:
```bash
python src/venn_event.py SmallReqScheduler MixedJob VennClient 50 config/even_workload.yml
python src/venn_event.py FIFOScheduler MixedJob VennClient 50 config/even_workload.yml
python src/venn_event.py VennReqScheduler MixedJob VennClient 50 config/even_workload.yml
```

To reproduce the rest of results in the paper, please check out `config` for the corresponding configurations. 

## Code Structure

The Venn project is organized as follows:

- **venn/**: Contains the core logic for the Venn resource management tool.
  - `venn_event.py`: Main script to simulate the scheduling for multiple federated learning jobs.
  - `scheduler.py`: Implements different scheduling algorithms.
  - `client.py`: Defines client behavior and interactions.
  - `job.py`: Manages job definitions and lifecycle.
- **config/**: Contains configuration files for FL job traces (resource demands and FL job type distribution). Check out `/config/test.yml` for more details.
- **trace/**: Contains configuration files for FL client traces (availability and eligiblity traces). 

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
