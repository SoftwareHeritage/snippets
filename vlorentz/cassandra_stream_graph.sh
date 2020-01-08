#!/bin/bash
set -e

PYTHON=python3
NB_PARTITIONS=16
TABLES="content directory directory_entry revision revision_parent release snapshot snapshot_branch origin_visit origin"
TABLES="revision"

tmp_dir=$(mktemp -td swh-graph-export.XXXXXXXXXX)
trap "rm -rf ${tmp_dir}; pkill -P $$" EXIT

nodes_fifo="${tmp_dir}/nodes.csv.fifo"
edges_fifo="${tmp_dir}/edges.csv.fifo"

mkfifo "${nodes_fifo}"
mkfifo "${edges_fifo}"


cat "${nodes_fifo}" | pigz -c > nodes.csv.gz &
cat "${edges_fifo}" | pigz -c > edges.csv.gz &

for table in ${TABLES}; do
    echo "Exporting ${table}"
    pids=""
    for ((partition_id=0;partition_id<NB_PARTITIONS;partition_id++)); do
        ${PYTHON} cassandra_stream_graph.py "${nodes_fifo}" "${edges_fifo}" --table "${table}" --nb-partitions "${NB_PARTITIONS}" --partition-id "${partition_id}" &
        pids+=($!)
    done
    for pid in ${pids[@]}; do
        wait "${pid}"
    done
done

wait
