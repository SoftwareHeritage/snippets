#!/bin/bash
set -e

PSQL_CONN="service=softwareheritage-dev"
if [ "$1" = "-h" -o "$1" = "--help" ] ; then
    echo "Usage: export-graph.sh [POSTGRES_CONNECTION_STRING]"
    exit 1
elif [ -n "$1" ] ; then
    PSQL_CONN="$1"
    shift
fi

tmp_dir=$(mktemp -td swh-graph.XXXXXXXXXX)
trap "rm -rf ${tmp_dir}" EXIT

fifo="${tmp_dir}/graph.fifo"
mkfifo "$fifo"

psql "$PSQL_CONN" < export-edges.sql \
    | tee "$fifo" | pigz -c > swh-graph.edges.csv.gz

tr ' ' '\n' < "$fifo" | sort -u | pigz -c > swh-graph.nodes.csv.gz

psql "$PSQL_CONN" < export-origins.sql | pigz -c > swh-graph.origins.csv.gz

echo "All done."
echo "- graph stored in: swh-graph.{nodes,edges}.csv.gz"
echo "- origins stored in: swh-graph.origins.csv.gz"
