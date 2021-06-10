#!/usr/bin/env bash

set -eu

SCRIPT_DIR="$(pwd $(dirname @0))"

source "${SCRIPT_DIR}/environment.cfg"

${SCRIPT_DIR}/02-reserve_nodes.sh

echo "########### Waiting for node installations"
while [ ! -e ${SCRIPT_DIR}/nodes.installed ]; do
    sleep 2
done
echo "########### Node installations done"

echo "########### Initialize cassandra"
FIRST_STORAGE_HOST="$(echo ${STORAGE_HOSTS} | cut -f1 -d' ')"
STORAGE_NODE="${FIRST_STORAGE_HOST}.${G5K_SITE}"

ssh "${SSH_USER}@${STORAGE_NODE}" /usr/local/bin/swh-storage-init-cassandra.sh

echo "####### FINISHED"

echo "####### Sleeping"
sleep infinity
