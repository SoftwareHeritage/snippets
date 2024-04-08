#!/bin/bash

# Generate the consumer offsets with:
# /opt/kafka/bin/kafka-consumer-groups.sh --bootstrap-server $SERVER --describe \
# --group swh-archive-prod-winery-content-replayer |grep -v PARTITION | awk '{print $3,$4}' \
# | sort -n > winery-partitions.lst


while read partition position
do
  python3 cli.py -p $partition -o $position -g
done
