#!/bin/bash
psql -a service=swh-replica < swh-graph.sql > swh-graph.out
