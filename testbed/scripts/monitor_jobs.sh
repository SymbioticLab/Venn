# /bin/bash

set -Eeuo pipefail

command_exists() {
    command -v "$1" >/dev/null
}

if ! command_exists multitail; then
    echo "Multitail is not installed. Installing it..."
    sudo apt-get update
    sudo apt-get install multitail
fi


multitail -s 3 -n 1 ./evaluation/monitor/job/*.log