#/bin/bash

cook() {
    dir_id="$1"
    curl -v --insecure -H 'Host: archive.softwareheritage.org' \
        -XGET "https://moma.internal.softwareheritage.org/api/1/vault/directory/$dir_id/raw/" \
        > $dir_id.tar.gz
}

cook "$1"
