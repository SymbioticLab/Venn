# /bin/bash

set -Eeuo pipefail
if [ $# -eq 0 ]; then
  echo "Error: Please provide a directory name as an argument."
  exit 1
fi

set -x 
dir_name="evaluation_result/$1"
mkdir $dir_name
mkdir "$dir_name/job"
mkdir "$dir_name/executor"

cp ./evaluation/monitor/job/*.csv "$dir_name/job"
cp ./evaluation/monitor/executor/*.csv "$dir_name/executor"

set +x