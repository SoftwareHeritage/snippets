#!/bin/bash

#OAR -l /nodes=1,walltime=15:00:00
#OAR -p n_cores=32
#OAR -n theStackV2-genDownloadList
#OAR --project pr-swh-codecommons
#OAR --stdout the-stack-v2_gen-download_list-OARstdout.log
#OAR --stderr the-stack-v2_gen-download_list-OARstderr.log

# submit with `oarsub -S $HOME/script.sh`

COUNTDOWN=$((OAR_JOB_WALLTIME_SECONDS-60))
echo "will cleanup in $COUNTDOWN"

VMSTAT_DIR="$HOME/resource_use_$OAR_JOB_ID"
mkdir -p $VMSTAT_DIR
vmstat -t -w -n -S M 1 &> "$VMSTAT_DIR/$HOSTNAME" & # /!\ the kill %1 at the end is important

$(sleep $COUNTDOWN; rm -rf /var/tmp/kirchgem )&

source /applis/site/guix-start.sh

python3 -u ./the-stack-v2_gen-download_list.py &>> the-stack-v2_gen-download_list-all.log

rm -rf /var/tmp/kirchgem
kill $(jobs -p)

