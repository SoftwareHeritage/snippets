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

NODE=$(uniq "${OAR_NODE_FILE}")
echo "${NODE}" >> ${SCRIPT_DIR}/besteffort_nodes.lst
sort besteffort_nodes.lst | uniq > besteffort_nodes.lst.tmp
mv besteffort_nodes.lst.tmp besteffort_nodes.lst

echo "${CASSANDRA_HOSTS}" | sed 's/ /,/g' > ${SCRIPT_DIR}/cassandra_seeds.lst

time rsync -avP  . "${SSH_USER}"@${NODE}:install 
time ssh ${SSH_OPTIONS} "${SSH_USER}"@${NODE} install/_provision_node.sh


# Refresh the monitoring configuration
time rsync -avP  . "${SSH_USER}"@${MONITORING_HOSTS}:install 
time ssh ${SSH_OPTIONS} "${SSH_USER}"@${MONITORING_HOSTS} install/_provision_node.sh
ssh ${SSH_OPTIONS} "${SSH_USER}"@${MONITORING_HOSTS} docker restart prometheus

# Start the replayers
${SCRIPT_DIR}/10-start_replayers.sh ${NODE}

# The script must not exit to avoid the oar job to be killed
echo "########### Sleeping"
sleep infinity
