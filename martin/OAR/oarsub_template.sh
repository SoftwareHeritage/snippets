#!/bin/bash

#OAR -l /core=1,walltime=00:30:00
#OAR -n testOARSUB
#OAR -t devel
#OAR --project pr-swh-codecommons
#OAR --stdout testing-OARstdout.log
#OAR --stderr testing-OARstderr.log

# submit with `oarsub -S $HOME/script.sh`

COUNTDOWN=$((OAR_JOB_WALLTIME_SECONDS-60))
echo "will cleanup in $COUNTDOWN"

VMSTAT_DIR="$HOME/resource_use_$OAR_JOB_ID"
mkdir -p $VMSTAT_DIR
vmstat -t -w -n -S M 1 &> "$VMSTAT_DIR/$HOSTNAME" & # /!\ the kill %1 at the end is important

$(sleep $COUNTDOWN; rm -rf /var/tmp/kirchgem )&

echo "started"
# python3 -u -c 'print("the -u (unbuffered) is important for future prints!")'
sleep 10
echo "nothing to do, stopping"

rm -rf /var/tmp/kirchgem
kill $(jobs -p)

