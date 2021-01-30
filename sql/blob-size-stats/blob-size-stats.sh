#!/bin/bash
time psql --csv service=swh-replica < blob-size-stats.sql > blob-size-stats.csv
