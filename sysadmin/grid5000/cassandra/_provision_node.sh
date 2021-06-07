#!/usr/bin/env bash

set -eux

apt update
apt install -y ansible

cd /root/install/ansible
CASSANDRA_SEEDS="$(cat ../cassandra_seeds.lst)"

ansible-playbook -i hosts.yml -l "$(hostname)" playbook.yml --extra-vars "cassandra_seed_ips=${CASSANDRA_SEEDS}"
