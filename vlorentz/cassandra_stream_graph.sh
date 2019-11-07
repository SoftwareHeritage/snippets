#!/bin/bash
set -e

tmp_dir=$(mktemp -td swh-graph-export.XXXXXXXXXX)
trap "rm -rf ${tmp_dir}; pkill -P $$" EXIT

nodes_fifo="${tmp_dir}/nodes.csv.fifo"
edges_fifo="${tmp_dir}/edges.csv.fifo"

mkfifo "${nodes_fifo}"
mkfifo "${edges_fifo}"

NB_PARTITIONS=16
for ((partition_id=0;partition_id<NB_PARTITIONS;partition_id++)); do
    python3 cassandra_stream_graph.py "${nodes_fifo}" "${edges_fifo}" --table revision --nb-partitions "${NB_PARTITIONS}" --partition-id "${partition_id}" &
done


cat "${nodes_fifo}" > nodes.csv &
cat "${edges_fifo}" > edges.csv &

wait
