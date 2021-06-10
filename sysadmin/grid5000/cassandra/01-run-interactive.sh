#!/usr/bin/env bash

set -eu

SCRIPT_DIR="$(pwd $(dirname @0))"

${SCRIPT_DIR}/02-reserve_nodes_interactive.sh
