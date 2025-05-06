# Venn: Resource Management Across Federated Learning Jobs

[![arXiv](https://img.shields.io/badge/arXiv-2312.08298v1-b31b1b.svg)](https://arxiv.org/abs/2312.08298)

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

2. Clone the repository:
```bash
git clone https://github.com/SymbioticLab/Venn
cd Venn
```

3. Create the conda environment:
```bash
conda env create -f environment.yml
conda activate venn_env
```

4. Download the FL job and client traces.
```bash
sudo apt update
sudo apt install git-lfs
git lfs install
git lfs pull            
```

## Usage
Run simulations for scheduling FL jobs using the following command:
```bash
python src/venn_event.py <Scheduler> <JobType> <ClientType> <NumJobs> <ClientAndJobTrace>
``` 

Commands to reproduce Table 1 line 1:
```bash
python src/venn_event.py SmallReqScheduler MixedJob VennClient 50 config/even_workload.yml
python src/venn_event.py FIFOScheduler MixedJob VennClient 50 config/even_workload.yml
python src/venn_event.py VennReqScheduler MixedJob VennClient 50 config/even_workload.yml
```

- Expected results (check out `fig/`):
  - `FIFOScheduler`: Average queuing delay: 246.436; Average job completion time (JCT): 4233961.563; Total makespan: 9069573.109
  - `SmallReqScheduler`: Average queuing delay: 345.579; Average job completion time (JCT): 3445766.367; Total makespan: 10739668.501
  - `VennReqScheduler`:  Average queuing delay: 321.743; Average job completion time (JCT): 3133770.735; Total makespan: 8742415.026

- Each experiment is expected to take approximately 1 hour to complete, depending on your machine's specifications.

- To reproduce additional results from the paper, refer to the config directory and replace <ClientAndJobTrace> with the corresponding configuration files.

## Code Structure

The Venn project is organized as follows:

- **venn/**: Contains the core logic for the Venn resource management tool.
  - `venn_event.py`: Main script to simulate the scheduling for multiple federated learning jobs.
  - `scheduler.py`: Implements different scheduling algorithms.
  - `client.py`: Defines client behavior and interactions.
  - `job.py`: Manages job definitions and lifecycle.
- **config/**: Contains configuration files for FL job traces (resource demands and FL job type distribution). Check out `config/test.yml` for more detailed explanations.
- **trace/**: Contains configuration files for FL client traces (availability and eligiblity traces).
- **testbed/**: Contains the code to run the testbed FL job scheduling experiments. Please check separate [instructions](./testbed/README.md) to setup Propius.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
