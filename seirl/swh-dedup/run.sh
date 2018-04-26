#!/bin/bash

#db_name=swh-dedup
#db_service=$db_name
#
#dropdb $db_name
#createdb $db_name
#psql service=$db_service -f swh-dedup-blocks.sql
#psql service=$db_service -f swh-dedup-blocks-methods.sql

time xzcat ~/content-samples/content-sample.0.1pct.txt.xz \
    | parallel --spreadstdin --pipe -L 10000 -P 24 python -m deduper
    #| head -n1000000 \
