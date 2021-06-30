#!/usr/bin/env bash

set -eu

NODES=$*

SCRIPT_DIR="$(pwd $(dirname @0))"

source "${SCRIPT_DIR}/environment.cfg"

if [ -z "${NODES}" ]; then
  NODES=${STORAGE_HOSTS}
fi

for NODE in $NODES; do
    echo "########### Stopping replayers on $NODE..."
    ssh "${SSH_USER}"@"${NODE}" 'cd /etc/systemd/system; ls replayer-*.target' | xargs -r ssh "${SSH_USER}"@"${NODE}" systemctl stop
done

echo "####### $0 FINISHED"
