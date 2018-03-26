#!/bin/bash

query=$( cat )

jq -n --arg v "$query" '{"query": $v}' | \
    curl -s -H "Authorization: bearer $( cat ~/.github_access_token )" \
         -X POST -d @- https://api.github.com/graphql
