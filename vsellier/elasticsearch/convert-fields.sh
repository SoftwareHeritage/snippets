#!/usr/bin/env bash
# set -x
set -e

export ES_NODE="192.168.100.61:9200"

export INDEX=$1

cat > /tmp/reindex.json <<EOF
{
  "source": {
    "index": "${INDEX}"
  },
  "dest": {
    "index": "${INDEX}.migrated"
  },
  "script": {
    "inline": "ctx._source.bytes = ctx._source.bytes instanceof java.lang.String ? Long.parseLong(ctx._source.bytes) : ctx._source.bytes; ctx._source.response = ctx._source.response instanceof java.lang.String ? Long.parseLong(ctx._source.response) : ctx._source.response;"
  }
}
EOF

DOCS_TO_MIGRATE=$(curl -s http://$ES_NODE/$INDEX/_stats  | jq '._all.primaries.docs.count')

echo "$DOCS_TO_MIGRATE documents to migrate"

curl -XPOST -H "Content-Type: application/json" http://$ES_NODE/_reindex\?pretty -d @/tmp/reindex.json

echo "Refreshing index stats"
curl -XPOST http://$ES_NODE/$INDEX.migrated/_refresh
echo

DOCS_MIGRATED=$(curl -s http://$ES_NODE/$INDEX.migrated/_stats  | jq '._all.primaries.docs.count')

echo "$DOCS_MIGRATED / $DOCS_TO_MIGRATE documents migrated"
if [ "${DOCS_MIGRATED}" != "${DOCS_TO_MIGRATE}" ]; then
  echo "ERROR: The number of documents are not equals"
  echo "Migration stopped, the .migrated index is left in place"
  exit 1
fi

echo
echo "Removing old index"
curl -f -XDELETE http://$ES_NODE/$INDEX\?pretty

cat > /tmp/rename.json <<EOF
{
  "source": {
    "index": "${INDEX}.migrated"
  },
  "dest": {
    "index": "${INDEX}"
  }
}
EOF

echo
echo "Renaming $INDEX.migrated to $INDEX..."
curl -f -XPOST -H "Content-Type: application/json" http://$ES_NODE/_reindex\?pretty -d @/tmp/rename.json

echo
echo "Removing $INDEX.migrated..."
curl -f -XDELETE http://$ES_NODE/$INDEX.migrated\?pretty

echo
echo "Done"

