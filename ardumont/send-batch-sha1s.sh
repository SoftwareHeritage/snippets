#!/usr/bin/env bash

# time to wait for scheduling the next batch
SLEEP_TIME=200
# number of contents to process as a batch
BATCH_SIZE=1000
# total number of contents to send in batch number in one iteration
NUMBER_CONTENTS=100000
START=$([ -f position_indexer ] && cat position_indexer || echo 0)

while true
do
    POSITION=$(($NUMBER_CONTENTS * $START))

    echo "Sending $NUMBER_CONTENTS new contents from $POSITION"
    python3 ./read_from_archive.py \
            --archive-path /srv/storage/space/lists/azure-rehash/contents-sha1-to-rehash.txt.gz \
            --start-position $POSITION \
            --read-lines $NUMBER_CONTENTS | \
        SWH_WORKER_INSTANCE=swh_indexer_orchestrator python3 -m swh.indexer.producer \
                           --batch $BATCH_SIZE
                           # --task-name rehash \
                           # --dict-with-key sha1
    START=$((START + 1))

    echo "Waiting for computations to be done"
    echo
    sleep $SLEEP_TIME
    echo $START > position_indexer
done
