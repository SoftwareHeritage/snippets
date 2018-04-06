#!/bin/bash

db_name=swh-dedup
db_service=$db_name

dropdb $db_name
createdb $db_name
psql service=$db_service -f swh-dedup-blocks.sql
psql service=$db_service -f swh-dedup-blocks-methods.sql

time \
find ~/swh-storage -type f -printf "%f\n" \
    | head -n200 \
    | sort \
    | python -m deduper
