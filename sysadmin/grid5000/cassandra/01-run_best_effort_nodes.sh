#!/usr/bin/env bash

set -eu

SCRIPT_DIR="$(pwd $(dirname @0))"

NODE_COUNT=4
while true
do
        date
        COUNT="$(oarstat -u | grep -c 'R besteffort')"
        if [ $COUNT -lt $NODE_COUNT ]; then
                ${SCRIPT_DIR}/02-add_best_effort_node.sh
        else
                echo "Node count ok (${COUNT})"
        fi
        sleep 60
done
