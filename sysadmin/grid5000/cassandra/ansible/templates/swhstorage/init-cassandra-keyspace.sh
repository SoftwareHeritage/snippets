#!/bin/bash

echo "
from swh.storage.cassandra import create_keyspace
create_keyspace({{ cassandra_seed_ips.split(',') }}, 'swh') " | python3
