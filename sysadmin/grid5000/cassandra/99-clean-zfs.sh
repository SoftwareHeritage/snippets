#!/usr/bin/env bash

# set -eu

SCRIPT_DIR="$(pwd $(dirname @0))"

source "${SCRIPT_DIR}/environment.cfg"

CASSANDRA_NODES="$(cat ${SCRIPT_DIR}/cassandra_seeds.lst | tr ',' '\n') "

echo "*********************"
echo "WARNING"
echo "*********************"
echo "Running this script will wipe out all the data of the cassandra cluster."
echo "cassandra nodes: $(cat ${SCRIPT_DIR}/cassandra_seeds.lst)"
echo "Are you sure?"
read -r

echo "Stopping cassandra"
echo -n ${CASSANDRA_NODES} | parallel -v -d' ' ssh "${SSH_USER}"@{} systemctl stop cassandra 

for node in ${CASSANDRA_NODES}; do
    echo "Removing zfs datasets on ${node}"
    POOLS="$(ssh "${SSH_USER}"@${node} zpool list -o name | grep -v -e NAME -e "no pool")"
    echo ${POOLS}
    for pool in ${POOLS}; do
        echo "   Removing ${pool}"
        ssh "${SSH_USER}"@${node} zpool destroy $pool
    done
done

echo "Done"
echo "Don't forget to re-run ansible or 03-deploy_nodes.sh to reconfigure the environment"
