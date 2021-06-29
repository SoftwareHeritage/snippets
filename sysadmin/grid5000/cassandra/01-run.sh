#!/usr/bin/env bash

set -eu

SCRIPT_DIR="$(pwd $(dirname @0))"

source "${SCRIPT_DIR}/environment.cfg"

rm -vf nodes.installed besteffort_nodes.installed nodes.lst besteffort_nodes.lst

${SCRIPT_DIR}/02-reserve_nodes.sh

echo "########### Waiting for node installations"
while [ ! -e ${SCRIPT_DIR}/nodes.installed ]; do
    sleep 2
done
echo "########### Node installations done"

${SCRIPT_DIR}/05-initialize_cassandra.sh

${SCRIPT_DIR}/10-start_replayers.sh



echo "####### FINISHED"

echo "####### Sleeping"
sleep infinity
