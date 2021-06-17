#!/usr/bin/env bash

set -eu

SCRIPT_DIR="$(pwd $(dirname @0))"

source "${SCRIPT_DIR}/environment.cfg"

EXCLUDED_HOSTS=""

for h in ${BEST_EFFORT_EXCLUDED_NODES}; do
  EXCLUDED_HOSTS="${EXCLUDED_HOSTS},'${h}.${G5K_SITE}'"
done
EXCLUDED_HOSTS="$(echo ${EXCLUDED_HOSTS} | cut -b2-)"
oarsub -l "{cluster='${BEST_EFFORT_CLUSTER}' and host not in (${EXCLUDED_HOSTS})}/nodes=1,walltime=12" -t deploy -t besteffort ${SCRIPT_DIR}/03-deploy_besteffort_nodes.sh
