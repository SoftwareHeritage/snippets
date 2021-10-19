#!/bin/bash

source_file=$1

name=$(basename $source_file .output)

csv=${name}.csv
stats=${name}.stats

strings $source_file | grep ' CSV' | cut -f5- -d: | cut -f1 -d '['  > $csv
python stats.py $csv > $stats

echo Statistics generated in $stats

less $stats
