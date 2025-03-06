#!/usr/bin/env python
#!/bin/bash

RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m' # no color

isPackageNotInstalled() {
  $1 --version &> /dev/null
  if [ $? -eq 0 ]; then
    echo "$1: Already installed"
  elif [[ $(uname -p) == 'arm' ]]; then
    install_dir=$HOME/miniconda
    wget https://repo.anaconda.com/miniconda/Miniconda3-latest-MacOSX-arm64.sh
    bash  Miniconda3-latest-MacOSX-arm64.sh -b -p  $install_dir
    export PATH=$install_dir/bin:$PATH
  else
    install_dir=$HOME/anaconda3
    wget https://repo.anaconda.com/archive/Anaconda3-2023.03-1-Linux-x86_64.sh
    bash Anaconda3-2023.03-1-Linux-x86_64.sh -b -p  $install_dir
    export PATH=$install_dir/bin:$PATH

  fi
}

isDockerNotInstalled() {
  docker --version &> /dev/null
  if [ $? -eq 0 ]; then
    echo "docker: Already installed"
  else
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo apt-key add -
    sudo add-apt-repository "deb [arch=amd64] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable"
    sudo apt-get update
    apt-cache policy docker-ce
    sudo apt-get install -y docker-ce
    sudo systemctl status docker
  fi
}

isDockerComposeNotInstalled() {
  docker compose version &> /dev/null
  if [ $? -eq 0 ]; then
    echo "docker compose: Already installed"
  else
    DOCKER_CONFIG=${DOCKER_CONFIG:-$HOME/.docker}
    mkdir -p $DOCKER_CONFIG/cli-plugins
    curl -SL https://github.com/docker/compose/releases/download/v2.20.3/docker-compose-linux-x86_64 -o $DOCKER_CONFIG/cli-plugins/docker-compose
    chmod +x $DOCKER_CONFIG/cli-plugins/docker-compose
    docker compose version
  fi
}


isPackageNotInstalled conda

conda init bash
PROPIUS_HOME=$(pwd)
echo export PROPIUS_HOME=$(pwd) >> ~/.bashrc
. ~/.bashrc

if [ "$1" == "--cuda" ]; then
    conda env create -f environment_cuda.yml
    conda activate propius
    conda install pytorch==1.12.1 torchvision==0.13.1 torchaudio==0.12.1 cudatoolkit=11.3 -c pytorch
    wget https://developer.download.nvidia.com/compute/cuda/10.2/Prod/local_installers/cuda_10.2.89_440.33.01_linux.run
    sudo apt-get purge nvidia-* -y
    sudo sh -c "echo 'blacklist nouveau\noptions nouveau modeset=0' > /etc/modprobe.d/blacklist-nouveau.conf"
    sudo update-initramfs -u
    sudo sh cuda_10.2.89_440.33.01_linux.run --override --driver --toolkit --samples --silent
    export PATH=$PATH:/usr/local/cuda-10.2/
    conda install cudatoolkit=10.2 -y
else
    conda env create -f environment.yml
    conda activate propius
fi

isDockerNotInstalled
isDockerComposeNotInstalled

pip install -e .

