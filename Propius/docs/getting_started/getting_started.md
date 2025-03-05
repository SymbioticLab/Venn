# Getting Started

- If your machine has GPU and you want to use CUDA, check [this](https://askubuntu.com/questions/799184/how-can-i-install-cuda-on-ubuntu-16-04) out
- Download Anaconda if not installed
```bash
wget https://repo.anaconda.com/archive/Anaconda3-2023.03-1-Linux-x86_64.sh
bash Anaconda3-2023.03-1-Linux-x86_64.sh
conda list
```
- If your disk space is not enough for the entire Anaconda package, you can consider installing [miniconda](https://educe-ubc.github.io/conda.html)
- Install docker and docker-compose
    - [docker installation guide (step 1)](https://www.digitalocean.com/community/tutorials/how-to-install-and-use-docker-on-ubuntu-16-04)
    - [docker compose](https://docs.docker.com/compose/install/linux/#install-the-plugin-manually)
- Navigate into `Propius` package, install and activate `propius` conda environment
    - If you are using cuda
    ```bash
    cd Propius
    conda env create -f environment_cuda.yml
    conda activate propius
    conda install pytorch==1.12.1 torchvision==0.13.1 torchaudio==0.12.1 cudatoolkit=11.3 -c pytorch
    ```
    - If you are not using cuda

    ```bash
    cd Propius
    conda env create -f environment.yml
    conda activate propius
    ```
- Setup packages and environment
```bash
PROPIUS_HOME=$(pwd)
echo export PROPIUS_HOME=$(pwd) >> ~/.bashrc
. ~/.bashrc
pip install -e .
```