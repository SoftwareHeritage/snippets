#!/usr/bin/env bash

set -eux

# Install the OS
kadeploy3 -e debian10-x64-big -f "${OAR_FILE_NODES}" -k ~/.ssh/id_rsa.pub
