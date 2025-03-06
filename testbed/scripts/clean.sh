#!/bin/bash
# Remove all logs. If you use docker, try sudo ./scripts/clean.sh

rm ./propius/monitor/log/* -f
rm ./propius/monitor/plot/* -f
rm ./propius/parameter_server/object_store/* -f
rm ./evaluation/monitor/client/* -f
rm ./evaluation/monitor/executor/* -f
rm ./evaluation/monitor/job/* -f