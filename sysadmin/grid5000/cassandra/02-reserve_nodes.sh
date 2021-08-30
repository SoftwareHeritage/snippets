#!/usr/bin/env bash

# set -eu

SCRIPT_DIR="$(pwd $(dirname @0))"

source "${SCRIPT_DIR}/environment.cfg"

NODE_FILTER=""
for node in ${CASSANDRA_HOSTS} ${STORAGE_HOSTS} ${JOURNAL_CLIENT_HOSTS} ${MONITORING_HOSTS}; do
  NODE_FILTER="${NODE_FILTER},'${node}.${G5K_SITE}'"
done

NODE_FILTER="$(echo ${NODE_FILTER} | sed 's/^,//')"
NODE_COUNT="$(echo ${NODE_FILTER} | tr ',' ' ' | wc -w)"

if [ -e OAR_JOB_ID ]; then
  echo "Running in reservation mode, nodes should be already reserved"
  ${SCRIPT_DIR}/03-deploy_nodes.sh
else
  echo "Reserving and installing nodes"
  # oarsub -l "{host in (${NODE_FILTER})}/nodes=${NODE_COUNT},walltime=${NODE_RESERVATION_DURATION}" -t deploy ${SCRIPT_DIR}/03-deploy_nodes.sh
  oarsub -r "${RESERVATION_DATE}" -l "{host in (${NODE_FILTER})}/nodes=${NODE_COUNT},walltime=${NODE_RESERVATION_DURATION}" -t deploy ${SCRIPT_DIR}/03-deploy_nodes.sh
  # -t besteffort
  # -r '2021-06-08 19:05:00'
fi
