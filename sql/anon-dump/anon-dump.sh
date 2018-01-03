#!/bin/bash
psql -a service=swh-replica < anon-dump.sql > anon-dump.log
