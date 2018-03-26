#!/bin/bash

github_query() {
    query=$( cat )

    jq -n --arg v "$query" '{"query": $v}' \
        | curl -s -H "Authorization: bearer $( cat ~/.github_access_token )" \
            -X POST -d @- https://api.github.com/graphql
}

extract_trees () {
    jq  --raw-output '.data.search.edges[].node.ref.target.tree.oid // empty'
}

cd "$( dirname $0 )"

tmpf=$( mktemp --suffix github-graphql-search )
cursor=""

for i in $( seq 1 5 ); do
    echo >&2 "Requesting page $i..."
    cat github_search.graphql \
        | sed 's/\(search(.\+\))/\1'"$cursor)/" \
        | github_query \
        > "$tmpf"
    extract_trees < "$tmpf"
    hasNext=$( jq --raw-output '.data.search.pageInfo.hasNextPage' "$tmpf" )
    if [ "$hasNext" != "true" ]; then
        break;
    fi
    cursor=$( jq --raw-output '.data.search.pageInfo.startCursor' "$tmpf" )
    cursor=", after:\"$cursor\""
done

rm "$tmpf"
