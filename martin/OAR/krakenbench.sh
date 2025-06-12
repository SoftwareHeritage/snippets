#!/bin/bash

#OAR -d /home/kirchgem/2025-06-11-firstGraphTest
#OAR -p "fat='YES'"
#OAR -l /nodes=2,walltime=6:00:00
#OAR --name graph-benchmark
#OAR --project pr-swh-codecommons
#OAR --stdout OARstdout.log
#OAR --stderr OARstderr.log

#--notify "mail:name\@domain.com"

source /applis/site/nix.sh

SWHHOME=/hoyt/pr-swh-codecommons
MOUNTPOINT=/var/tmp/kirchgem/mountpoint
export SWH_CONFIG_FILE=./config.yml
export PATH="$HOME:$PATH"

vmstat -t -w -n -S M 10 &> resource_use_$HOSTNAME &

# TODO: only head node has a non-empty $OAR_NODE_FILE
# headnode=$(cat $OAR_NODE_FILE | grep -- "-f" | sort -u | head -n 1)

if [ "$HOSTNAME" == "$HOSTNAME" ];
then
    echo "I'm $HOSTNAME and I'm the head node"
    RUST_LOG=warn swh-graph-grpc-serve --direction forward $SWHHOME/2024-12-06-minimalgraph/graph &> $HOSTNAME-grpc-serve.log &
    sleep 20

    cat > $SWH_CONFIG_FILE <<EOF
swh:
  fuse:
    cache:
      metadata:
        in-memory: true
      blob:
        bypass: true
      direntry:
        maxram": "1%"
    graph:
      grpc-url: $HOSTNAME:50091
    content:
      storage:
        cls: digestmap
        path: "$SWHHOME/the-stack-v2-digestmap/"
      objstorage:
        cls: http
        url: https://softwareheritage.s3.amazonaws.com/content/
        compression: gzip
        retry:
          total: 3
          backoff_factor: 0.2
          status_forcelist:
            - 404
            - 500
EOF

    # TODO how to turn off the grpc-server ??
    sleep 5h

else
    while [ ! -f $SWH_CONFIG_FILE ]
    do
      echo $(date) " $HOSTNAME waiting for the graph-grpc-server to start and create the config..." &>> $HOSTNAME-mount.log
      sleep 20
    done

    mkdir -p $MOUNTPOINT
    # swh --log-level swh.fuse:DEBUG, maybe
    unshare --pid --kill-child --user --map-root-user --mount swh fs mount -f $MOUNTPOINT &>> $HOSTNAME-mount.log &
    sleep 3
    MOUNTED=/proc/$(ps -C .swh-wrapped -o pid=)/root${MOUNTPOINT}

    echo "mounted on $MOUNTED:" &>> $HOSTNAME-mount.log
    ls $MOUNTED &>> $HOSTNAME-mount.log

    krakenbench.py pythonfiles $SWHHOME/the-stack-v2-directoryIDs 2 2 $MOUNTED &>> $HOSTNAME-bench.log

    sleep 5h


fi

kill $(jobs -p)
