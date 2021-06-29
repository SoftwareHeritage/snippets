#!/bin/bash

REPLICATION_FACTOR=$1

if [ -z "${REPLICATION_FACTOR}" ]; then
  echo "usage: $0 <replication factor>"
  exit 1
fi

echo "Changing replication factor"
echo "ALTER KEYSPACE swh
WITH 
replication = 
{
'class': 'SimpleStrategy', 
'replication_factor': '3'
}; 
" | cqlsh "$(facter networking.ip)"

echo "Launching repair..."
nodetool repair --full
