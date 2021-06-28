#!/usr/bin/env bash

#set -eux

apt update
apt install -y ansible

cd /root/install/ansible
CASSANDRA_SEEDS="$(cat ../cassandra_seeds.lst)"
NODES="$(cat ../nodes.lst ../besteffort_nodes.lst | tr '\n' ',')"

ansible-playbook -i hosts.yml -e @/root/install/.credentials --vault-password-file=/root/install/.vault_password -l "$(hostname)" playbook.yml --extra-vars "cassandra_seed_ips=${CASSANDRA_SEEDS}" --extra-vars "nodes=${NODES}"
