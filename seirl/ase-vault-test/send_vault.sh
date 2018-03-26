#/bin/bash

cook() {
    dir_id="$1"
    curl --insecure -s -H 'Host: archive.softwareheritage.org' \
        -XPOST "https://moma.internal.softwareheritage.org/api/1/vault/directory/$dir_id/" \
        | jq --raw-output '.status'
}

cook "$1"
