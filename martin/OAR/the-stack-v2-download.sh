#!/bin/bash

#OAR -l /nodes=1/cpu=1/core=16,walltime=24:00:00
#OAR --array 2
#OAR -n theStackV2-download
#OAR --project pr-swh-codecommons
#OAR --stdout the-stack-v2-download_logs/theStackV2-download-OARstdout.log
#OAR --stderr the-stack-v2-download_logs/theStackV2-download-OARstderr.log

# submit with `oarsub -S $HOME/script.sh`

source /applis/site/guix-start.sh
LOG=$HOME/the-stack-v2-download_logs/batch-$OAR_JOB_ID-$HOSTNAME.log
/usr/bin/time -f 'max res size: %M KB' python3 -u ./the-stack-v2_download.py &>> $LOG
