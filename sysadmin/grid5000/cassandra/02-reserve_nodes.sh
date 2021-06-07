#!/usr/bin/env bash

set -eu

SCRIPT_DIR="$(pwd $(dirname @0))"

source "${SCRIPT_DIR}/environment.cfg"

NODE_FILTER=""
for node in ${CASSANDRA_HOSTS} ${STORAGE_HOSTS} ${JOURNAL_CLIENT_HOSTS} ${MONITORING_HOSTS}; do
  NODE_FILTER="${NODE_FILTER},'${node}.${G5K_SITE}'"
done

NODE_FILTER="$(echo ${NODE_FILTER} | sed 's/^,//')"
NODE_COUNT="$(echo ${NODE_FILTER} | tr ',' ' ' | wc -w)"

oarsub -r '2021-06-08 19:05:00' -l "{host in (${NODE_FILTER})}/nodes=${NODE_COUNT},walltime=${NODE_RESERVATION_DURATION}" -t deploy ${SCRIPT_DIR}/03-deploy_nodes.sh
# -t besteffort
# -r '2021-06-08 19:05:00'
