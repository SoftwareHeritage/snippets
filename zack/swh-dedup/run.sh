#!/bin/bash

db_name=swh-dedup
db_service=$db_name

sudo -u postgres dropdb -p 5433 $db_name
sudo -u postgres createdb -p 5433 -O swhdev $db_name
psql service=$db_service -f swh-dedup-blocks.sql

time \
find /srv/softwareheritage/objects -type f \
    | sort \
    | cut -f 7 -d/ \
    | ./swh-dedup-blocks.py
