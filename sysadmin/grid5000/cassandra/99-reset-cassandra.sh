#!/usr/bin/env bash

set -eu

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

echo "Removing data"
echo -n ${CASSANDRA_NODES} | parallel -v -d' ' ssh "${SSH_USER}"@{} rm -rf "/srv/cassandra/commitlog/*" "/srv/cassandra/data/*"

echo "Starting cassandra"
echo -n ${CASSANDRA_NODES} | parallel -v -d' ' ssh "${SSH_USER}"@{} systemctl start cassandra 

echo "Starting cassandra"
echo -n ${CASSANDRA_NODES} | parallel -v -d' ' ssh "${SSH_USER}"@{} systemctl start cassandra 


echo "Done"
