#!/bin/bash

# set -x
set -o pipefail

FIRST_PARTITION=0
LAST_PARTITION=255

# Number of parallel processes to execute
# can be changed dynamically by changing the value in `.processes` file
NB_PROCESSES=1
PROCESS_FILE=.processes

echo ${NB_PROCESSES} > ${PROCESS_FILE}

check_processes() {
  local max=$(cat ${PROCESS_FILE})
  local current=$(jobs | wc -l)

  if [ ${current} -ge ${max} ]; then
    sleep 30 &
    wait -n
    check_processes
  fi

}

for partition in $(seq ${FIRST_PARTITION} ${LAST_PARTITION}); do
  echo Checking $partition

  base=/var/tmp/checker/id_to_check_${partition}
  input=${base}.lst
  errors=${base}.errors
  output=${base}.output
  done=${base}.done

  (unbuffer time python3 cli.py -o $(wc -l ${input} | awk '{print $1}') \
    --output-file ${errors} \
    -c ${input} | tee ${output} && touch ${done}) &

  sleep .5
  check_processes
done

echo waiting for the last processes to finish
wait
