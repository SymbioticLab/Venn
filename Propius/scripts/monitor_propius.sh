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

sc_log="./propius/monitor/log/sc.log"
jm_log="./propius/monitor/log/jm.log"
cm0_log="./propius/monitor/log/cm_0.log"
cm1_log="./propius/monitor/log/cm_1.log"

multitail -s 2 -n 1 -l "tail -f $sc_log" -l "tail -f $jm_log" -l "tail -f $cm0_log" -l "tail -f $cm1_log"