#!/usr/bin/env bash

# set -eux

SCRIPT_DIR="$(pwd $(dirname @0))"

source "${SCRIPT_DIR}/environment.cfg"

echo "########### Nodes:"
uniq "${OAR_FILE_NODES}"
echo "########### Installing os on nodes"

INSTALLED_OS_STAMP="${OAR_JOB_ID}.os.stamp"

if [ ! -e "${SCRIPT_DIR}/${INSTALLED_OS_STAMP}" ]; then
    ${SCRIPT_DIR}/_install_os.sh
    touch "${SCRIPT_DIR}/${INSTALLED_OS_STAMP}"
fi

uniq "${OAR_NODE_FILE}" > ${SCRIPT_DIR}/nodes.lst

NODE_COUNT="$(wc -l ${SCRIPT_DIR}/nodes.lst | cut -f1 -d' ')"

echo "${CASSANDRA_HOSTS}" | sed 's/ /,/g' > ${SCRIPT_DIR}/cassandra_seeds.lst

time parallel -j${NODE_COUNT} rsync -avP  . "${SSH_USER}"@{}:install < ${SCRIPT_DIR}/nodes.lst

time parallel -j${NODE_COUNT} -u ssh ${SSH_OPTIONS} "${SSH_USER}"@{} install/_provision_node.sh < ${SCRIPT_DIR}/nodes.lst

echo "########### Cassandra installation done"
touch ${SCRIPT_DIR}/nodes.installed

# The script must not exit to avoid the oar job to be killed
echo "########### Sleeping"
sleep infinity
