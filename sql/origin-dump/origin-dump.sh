#!/bin/bash
psql -a service=swh-replica < origin-dump.sql > origin-dump.log
