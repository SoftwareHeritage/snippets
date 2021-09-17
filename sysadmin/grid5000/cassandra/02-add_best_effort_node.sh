#!/usr/bin/env bash

set -eu

SCRIPT_DIR="$(pwd $(dirname @0))"

source "${SCRIPT_DIR}/environment.cfg"

EXCLUDED_HOSTS=""

if [ -n "${EXCLUDED_HOSTS}" ]; then
  TO_EXCLUDE=" and host not in ($(echo ${BEST_EFFORT_EXCLUDED_NODES} | sed 's/,/ /g'))"
else
  TO_EXCLUDE=""
fi
  
for h in ${TO_EXCLUDE}; do
  EXCLUDED_HOSTS="${EXCLUDED_HOSTS},'${h}.${G5K_SITE}'"
done

oarsub -l "{cluster='${BEST_EFFORT_CLUSTER}' ${TO_EXCLUDE}}/nodes=1,walltime=12" -t deploy -t besteffort ${SCRIPT_DIR}/03-deploy_besteffort_nodes.sh
