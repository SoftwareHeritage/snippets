#!/usr/bin/env bash

set -eu

SCRIPT_DIR="$(pwd $(dirname @0))"

source "${SCRIPT_DIR}/environment.cfg"

FIRST_STORAGE_HOST="$(echo ${STORAGE_HOSTS} | cut -f1 -d' ')"
STORAGE_NODE="${FIRST_STORAGE_HOST}.${G5K_SITE}"

FIRST_CASSANDRA_HOST="$(echo ${CASSANDRA_HOSTS} | cut -f1 -d' ')"
CASSANDRA_NODE="${FIRST_CASSANDRA_HOST}.${G5K_SITE}"

echo "########### Initialize cassandra keyspace..."
ssh "${SSH_USER}@${STORAGE_NODE}" /usr/local/bin/swh-storage-init-cassandra.sh

echo "########### Change the replication factor..."
ssh "${SSH_USER}@${CASSANDRA_NODE}" /usr/local/bin/change-cassandra-replication.sh "${CASSANDRA_REPLICATION_FACTOR}"

echo "####### $0 FINISHED"
