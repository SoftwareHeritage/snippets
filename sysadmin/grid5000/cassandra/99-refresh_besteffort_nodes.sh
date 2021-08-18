#!/usr/bin/env bash

set -eu

SCRIPT_DIR="$(pwd $(dirname @0))"

source "${SCRIPT_DIR}/environment.cfg"

JOBS="$(oarstat -u | grep 'R besteffort' | cut -f1 -d' ' | grep '^[0-9]')"

TMP_FILE=besteffort_nodes.lst.tmp
TARGET_FILE=besteffort_nodes.lst

# create an empty file, and ensure its empty
echo -n > ${TMP_FILE}

for j in $JOBS; do
    echo Getting $j job host...
    h="$(oarstat -fj $j | grep hostname | awk '{print $3}')"
    echo -n "    $h:"
    if [ -e "${SCRIPT_DIR}/${j}.os.stamp" ]; then
        echo " host installed"
        echo "$h" >> ${TMP_FILE}
    else
        echo " host not yet installed, ignoring it"
    fi
done

sort ${TMP_FILE} > ${TARGET_FILE}

echo "$(wc -l ${TARGET_FILE} | cut -f1 -d' ') hosts found"

echo "Done"
