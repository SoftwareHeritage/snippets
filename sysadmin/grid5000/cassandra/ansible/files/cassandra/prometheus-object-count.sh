#!/bin/bash

outfile="/var/lib/prometheus/node-exporter/swhobjectscount.prom"
tmpfile=$(mktemp /tmp/count.XXXXXX)

cleanup() {
    rm -f "$tmpfile"
}
trap cleanup INT TERM EXIT

cqlsh "$(facter networking.ip)" -k swh -e "copy object_count (object_type, count) to '/tmp/count'"

echo '# TYPE swh_objects_total gauge' >"${tmpfile}"

while read object_type count; do
  echo "swh_objects_total{type=\"${object_type}\"} ${count}" >> "${tmpfile}"
done <<<"$(cat /tmp/count | tr ',' ' ' | tr -d '\r')"

chmod 644 "$tmpfile"
mv "$tmpfile" "$outfile"
