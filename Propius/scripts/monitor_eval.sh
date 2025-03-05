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

exe_log="./evaluation/monitor/executor/exe.log"
wk0_log="./evaluation/monitor/executor/wk_0.log"
wk1_log="./evaluation/monitor/executor/wk_1.log"
wk2_log="./evaluation/monitor/executor/wk_2.log"
wk3_log="./evaluation/monitor/executor/wk_3.log"
sc_log="./propius/monitor/log/sc.log"
jm_log="./propius/monitor/log/jm.log"

multitail -s 3 -n 1 -l "tail -f $sc_log" -l "tail -f $jm_log" -l "tail -f $exe_log" -l "tail -f $wk0_log" -l "tail -f $wk1_log" -l "tail -f $wk2_log" -l "tail -f $wk3_log" 