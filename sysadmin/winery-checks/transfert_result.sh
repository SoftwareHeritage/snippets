#!/bin/bash

set -x

export POD=winery-checks-vse

for i in $(seq 0 255)
do
  SOURCE=id_to_check_${i}.lst
  echo transfering partition ${SOURCE} from pod

  echo "Checksum check..."
  kubectl cp --context archive-production-rke2 -n swh \
      $POD:snippets/sysadmin/winery-checks/${SOURCE}.md5 \
      ${SOURCE}.md5
  if [ -e ${SOURCE}.done ]; then
    echo "${SOURCE} already transferred to the CEA"
  elif ! md5sum -c ${SOURCE}.md5; then
    echo "Checksum incorrect, transferring the file from the pod"

    kubectl cp --context archive-production-rke2 -n swh \
        $POD:snippets/sysadmin/winery-checks/${SOURCE} \
        ${SOURCE}
  else
    echo "File is ok locally"
  fi

  echo launching transfert to CEA in background
  (rsync -azP ${SOURCE} gloin002:/var/tmp/checker/ && touch ${SOURCE}.done) &

  echo "------"

done

echo "Waiting for the end of the CEA transfers"
wait
