#!/bin/bash
# From FedScale
# https://github.com/SymbioticLab/FedScale/blob/master/benchmark/dataset/download.sh

RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m' # no color
DIR="$PROPIUS_HOME/datasets" 
ARGS=${@: 2};

set -Eeuo pipefail

Help()
{
   # Display Help
   echo 
   echo "Propius provides a large suite of FL datasets"
   echo
   echo "Syntax: download/remove [dataset_name]"
   echo "options:"
   echo "help                         Print this Help."
   echo "download                     Download dataset"
   echo "remove                       Remove dataset"

   echo
   echo "======= Available datasets ======="
   echo "speech                       Speech Commands dataset (about 2.3GB)"
   echo "open_images                  Open Images dataset (about 66GB)"
#    echo "amazon_review                Amazon Review dataset (about 11G)"
#    echo "charades                     Charades dataset (about 15G)"
#    echo "europarl                     Europarl dataset (about 458M)"
#    echo "go                           Go dataset (about 1.7G)"
#    echo "inaturalist                  Inaturalist 2019 dataset meta file (about 11M)"
#    echo "libriTTS                     LibriTTS dataset (about 78G)"
#    echo "open_images_detection        Open Images for detection (about 451M)"
#    echo "reddit                       Reddit dataset (about 25G)"
#    echo "taobao                       Taobao dataset (about 185M)"
#    echo "taxi                         Taxi Trajectory dataset (about 504M)"
#    echo "waymo                        Waymo Motion dataset meta file (about 74M)"
   echo "femnist                      FEMNIST dataset (about 327M)"
#    echo "stackoverflow                StackOverflow dataset (about 13G)"
#    echo "blog                         Blog dataset (about 833M)"
#    echo "common_voice                 Common Voice dataset (about 87G)"
#    echo "coqa                         CoQA dataset (about 7.9M)"
#    echo "puffer                       Puffer dataset (about 2.0G)"
#    echo "landmark                     Puffer dataset (about 954M)"
}

speech()
{
    if [ ! -d "${DIR}/speech_commands/train/" ];
    then
        echo "Downloading Speech Commands dataset(about 2.4GB)..."
        wget -O ${DIR}/google_speech.tar.gz https://fedscale.eecs.umich.edu/dataset/google_speech.tar.gz

        echo "Dataset downloaded, now decompressing..."
        tar -xf ${DIR}/google_speech.tar.gz -C ${DIR}

        echo "Removing compressed file..."
        rm -f ${DIR}/google_speech.tar.gz

        echo -e "${GREEN}Speech Commands dataset downloaded!${NC}"
    else
        echo -e "${RED}Speech Commands dataset already exists under ${DIR}/speech_commands/!"
fi
}


femnist()
{
    if [ ! -d "${DIR}/femnist/client_data_mapping" ]; then
        echo "Downloading FEMNIST dataset(about 327M)..."
        wget -O ${DIR}/femnist.tar.gz https://fedscale.eecs.umich.edu/dataset/femnist.tar.gz

        echo "Dataset downloaded, now decompressing..."
        tar -xf ${DIR}/femnist.tar.gz -C ${DIR}

        echo "Removing compressed file..."
        rm -f ${DIR}/femnist.tar.gz

        echo -e "${GREEN}FEMNIST dataset downloaded!${NC}"
    else
        echo -e "${RED}FEMNIST dataset already exists!"
    fi
}

open_images()
{
    if [ ! -d "./datasets/open_images/train/" ];
    then
        echo "Downloading Open Images dataset(about 66GB)..."
        wget -O ${DIR}/open_images.tar.gz https://fedscale.eecs.umich.edu/dataset/openImage.tar.gz

        echo "Dataset downloaded, now decompressing..."
        tar -xf ${DIR}/open_images.tar.gz -C ${DIR}

        echo "Removing compressed file..."
        rm -f ${DIR}/open_images.tar.gz

        echo -e "${GREEN}Open Images dataset downloaded!${NC}"
    else
        echo -e "${RED}Open Images dataset already exists under ${DIR}/open_images/!"
fi
}

Download() {
    for data in $ARGS
    do  
        echo "Downloading ${data}"
        case $data in
            speech )
                speech
                ;;
            open_images )
                open_images
                ;;
            femnist )
                femnist

                ;;
        esac
    done
}

Remove() {
    # Here we assume the folder name is the same to the dataset name
    for data in $ARGS
    do  
        echo "Removing ${data}"
        case $data in
            speech )
                rm -rf  ${DIR}/$data;
                ;;
            open_images )
                rm -rf  ${DIR}/$data;
                ;;
            femnist )
                rm -rf  ${DIR}/$data;
                ;;
        esac
    done
}

case "$1" in
    help ) # display Help
        Help
        ;;
    download )
        Download
        ;;
    remove )
        Remove 
        ;;
    + )
        echo "${RED}Usage: check help${NC}"
        Help
        ;;
    * )
        echo "${RED}Usage: check help${NC}"
        Help
    ;;
esac

