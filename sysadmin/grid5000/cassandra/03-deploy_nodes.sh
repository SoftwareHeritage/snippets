#!/usr/bin/env bash

# set -eu

SCRIPT_DIR="$(pwd $(dirname @0))"

source "${SCRIPT_DIR}/environment.cfg"

INSTALL_USER=root

echo "########### Nodes:"
uniq "${OAR_FILE_NODES}"
echo "########### Installing os on nodes"

INSTALLED_OS_STAMP="${OAR_JOB_ID}.os.stamp"

if [ ! -e "${SCRIPT_DIR}/${INSTALLED_OS_STAMP}" ]; then
    ${SCRIPT_DIR}/_install_os.sh
    touch "${SCRIPT_DIR}/${INSTALLED_OS_STAMP}"
fi

uniq "${OAR_NODE_FILE}" > ${SCRIPT_DIR}/nodes.lst

echo "${CASSANDRA_HOSTS}" | sed 's/ /,/' > ${SCRIPT_DIR}/cassandra_seeds.lst

parallel rsync -avP . "${INSTALL_USER}"@{}:install < ${SCRIPT_DIR}/nodes.lst

time parallel -u ssh "${INSTALL_USER}"@{} install/_provision_node.sh < ${SCRIPT_DIR}/nodes.lst

echo "########### Cassandra installation done"
touch ${SCRIPT_DIR}/nodes.installed

# The script must not exit to avoid the oar job to be killed
echo "########### Sleeping"
sleep infinity
