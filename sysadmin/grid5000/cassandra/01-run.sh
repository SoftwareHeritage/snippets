#!/usr/bin/env bash

set -eu

SCRIPT_DIR="$(pwd $(dirname @0))"

${SCRIPT_DIR}/02-reserve_nodes.sh

echo "########### Waiting for node installations"
while [ ! -e ${SCRIPT_DIR}/nodes.installed ]; do
    sleep 2
done
echo "########### Node installations detected"
