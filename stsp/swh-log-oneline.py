#!/usr/bin/python3
# Copyright (C) 2021  The Software Heritage developers
# License: GNU Affero General Public License version 3, or any later version
# See top-level LICENSE file for more information

# Starting from a given revision, display one-line summaries for each revision in history.
# Output is not identical but similar to: git log --pretty=oneline

import sys
import time

from swh.storage import get_storage
from swh.model.hashutil import hash_to_bytes
from swh.storage.algos.revisions_walker import get_revisions_walker

if __name__ == "__main__":
    if len(sys.argv) == 2:
        rev_id = hash_to_bytes(sys.argv[1])
        storage_url = "http://127.0.0.1:5002"
    elif len(sys.argv) == 3:
        rev_id = hash_to_bytes(sys.argv[1])
        storage_url = sys.argv[2]
    else:
        print("usage: revision [storage-url]")
        sys.exit(1)

    storage = get_storage("remote", url=storage_url)

    revs_walker = get_revisions_walker('committer_date', storage, rev_id)
    for rev in revs_walker:
        print("%s %s %s: %s" % (
            time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(rev['date']['timestamp']['seconds'])),
            rev['id'].hex(),
            rev['committer']['fullname'].decode('utf-8'),
            rev['message'].splitlines()[0].decode('utf-8')
            ))
