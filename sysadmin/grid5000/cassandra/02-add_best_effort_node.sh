#!/usr/bin/env bash

set -eu

SCRIPT_DIR="$(pwd $(dirname @0))"

source "${SCRIPT_DIR}/environment.cfg"

oarsub -l "{cluster='${BEST_EFFORT_CLUSTER}'}/nodes=1,walltime=12" -t deploy -t besteffort ${SCRIPT_DIR}/03-deploy_besteffort_nodes.sh
