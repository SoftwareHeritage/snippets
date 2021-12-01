#!/usr/bin/python3
# Copyright (C) 2021  The Software Heritage developers
# License: GNU Affero General Public License version 3, or any later version
# See top-level LICENSE file for more information

# Display a unified diff showing the changes made in a revision.

import sys
import difflib

from swh.storage import get_storage
from swh.model.hashutil import hash_to_bytes
from swh.storage.algos.diff import diff_revision

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

    diffs = diff_revision(storage, rev_id)
    for d in diffs:
        if d['type'] == 'modify':
            from_path = d['from_path']
            to_path = d['to_path']
            from_data = storage.content_get_data(d['from']['sha1'])
            to_data = storage.content_get_data(d['to']['sha1'])
        elif d['type'] == 'insert':
            from_path = b'/dev/null'
            to_path = d['to_path']
            from_data = b''
            to_data = storage.content_get_data(d['to']['sha1'])
        elif d['type'] == 'delete':
            from_path = d['to_path']
            to_path = b'/dev/null'
            from_data = storage.content_get_data(d['from']['sha1'])
            to_data = b''
        else:
            continue

        unidiff = difflib.diff_bytes(difflib.unified_diff,
            from_data.splitlines(keepends=True),
            to_data.splitlines(keepends=True),
            from_path, to_path)
        sys.stdout.buffer.writelines(unidiff);
