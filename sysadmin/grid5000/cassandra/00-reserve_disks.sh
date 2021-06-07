#!/usr/bin/env bash

set -eu

SCRIPT_DIR="$(pwd $(dirname @0))"
cd "${SCRIPT_DIR}"

source "${SCRIPT_DIR}/environment.cfg"

NODE_FILTER=""
for node in ${CASSANDRA_HOSTS} ${STORAGE_HOSTS} ${JOURNAL_CLIENT_HOSTS} ${MONITORING_HOSTS}; do
  NODE_FILTER="${NODE_FILTER},'${node}.${G5K_SITE}'"
done

NODE_FILTER="$(echo ${NODE_FILTER} | sed 's/^,//')"
NODE_COUNT="$(echo ${NODE_FILTER} | tr ',' ' ' | wc -w)"

oarsub -t noop -l "{type='disk' and host in (${NODE_FILTER})}/host=${NODE_COUNT}/disk=${CASSANDRA_DISKS_COUNT},walltime=${DISK_RESERVATION_DURATION}"
