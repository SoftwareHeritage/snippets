# Copyright (C) 2020 The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information

# use:
# python -m analyse_hash_collision \
#   --data-file hash-collisions.json \
#   | jq . > summary-collisions.json

import ast
import json

from collections import defaultdict
from typing import Any, Dict, Iterable, Tuple

import click

from swh.model.hashutil import (
    DEFAULT_ALGORITHMS, hash_to_hex, hash_to_bytes
)
from swh.storage import get_storage as get_swhstorage


storage = None


def get_storage():
    global storage
    if not storage:
        storage = get_swhstorage(
            cls='remote',
            url='http://uffizi.internal.softwareheritage.org:5002'
        )

    return storage


def import_data(f):
    return json.loads(open(f).read())


def content_get_metadata(
        content_ids: Iterable[str]) -> Dict[bytes, Dict[str, Any]]:
    """Retrieve content hashes from storage

    """
    content_bytes_ids = [
        hash_to_bytes(hhash_id) for hhash_id in list(content_ids)
    ]
    contents = get_storage().content_get_metadata(content_bytes_ids)
    result = {}
    for hash_id, all_contents in contents.items():
        count = len(all_contents)
        if count == 0:  # unexpected?
            continue
        # to ease comparison:
        # - take only 1 of the contents (most cases i guess)
        # - drop the length
        hashes = all_contents[0]
        hashes.pop('length', None)
        result[hash_id] = hashes

    return result


def content_find(content: Dict[str, bytes]) -> Dict[str, bytes]:
    """Retrieve content from the storage

    """
    c = get_storage().content_find(content)
    return c[0]


def content_hex_hashes(
        content: Dict[str, bytes], with_details=False) -> Dict[str, str]:
    """Convert bytes hashes into hex hashes.

    """
    c = content.copy()
    for algo in DEFAULT_ALGORITHMS:
        c[algo] = hash_to_hex(content[algo])
    ctime = c.get('ctime')
    if ctime:
        c['ctime'] = ctime.isoformat()
    return c


def content_equal(content0: Dict, content1: Dict) -> bool:
    """Check if content are equals solely comparing their hashes

    """
    for algo in DEFAULT_ALGORITHMS:
        if content0[algo] != content1[algo]:
            return False
    return True


def compute_diff_hashes(
        content0: Dict[str, str], content1: Dict[str, str]) -> Tuple[
            bool, Dict[str, str]]:
    """Compute the specific different between content

    """
    falsy = False
    diff_hashes = {}
    for algo in DEFAULT_ALGORITHMS:
        hash0 = content0[algo]
        hash1 = content1[algo]

        if hash0 != hash1:
            diff_hashes[algo] = [hash0, hash1]
            # different length is a smell for falsy collisions
            falsy = len(hash0) != len(hash1)

    return falsy, diff_hashes


@click.command()
@click.option('--data-file', default='hash-collision-all-sentry-id-1438.json')
def main(data_file):
    data = import_data(data_file)

    # how many collisions skipped due to incomplete message
    summary_skipped = 0
    # how many collisions
    summary_count = defaultdict(int)
    # one hash ends up with multiple collisions
    detailed_collisions = defaultdict(list)
    count = 0
    for entry_id, entry in data.items():
        message = entry['message']
        count += 1

        if message.endswith('...'):
            # TOOD: Find a way to retrieve the full message
            # because it can't be parsed for now
            summary_skipped += 1
            # incomplete message, skipping for now
            continue

        date_created = entry['date-created']
        msg: Tuple[str, bytes, Dict[str, bytes]] = ast.literal_eval(message)
        algo, hash_id, colliding_contents = msg
        if isinstance(hash_id, bytes):
            # old format
            # both hash_id and colliding_contents are using hash as bytes
            hex_hash_id = hash_to_hex(hash_id)
            colliding_contents = [
                content_hex_hashes(c) for c in colliding_contents
            ]
        else:
            hex_hash_id = hash_id
        # In the new hash collision format, hash_id and colliding_contents uses
        # hex hashes so nothing to do

        # Asserting we only have sha1 collisions so far
        assert algo == 'sha1'

        summary_count[hex_hash_id] += 1

        # take only 1 content, on previous iteration, the list was multiple
        # occurences of the same hash
        assert len(colliding_contents) == 1
        sentry_content = colliding_contents[0]
        sentry_content['date-reported-by-sentry'] = date_created
        detailed_collisions[hex_hash_id] = sentry_content

    # Retrieve the contents from storage to compare
    full_contents = content_get_metadata(summary_count.keys())

    count_collisions = 0
    count_falsy_collisions = 0
    collisions = {}
    falsy_collisions = {}
    for hash_id, stored_content in full_contents.items():
        hex_hash_id = hash_to_hex(hash_id)
        collision_content_hhashes = detailed_collisions[hex_hash_id]
        stored_content_hhashes = content_hex_hashes(stored_content)

        if content_equal(collision_content_hhashes, stored_content_hhashes):
            continue

        falsy, diff_hashes = compute_diff_hashes(
            stored_content_hhashes, collision_content_hhashes)

        if falsy:
            count_falsy_collisions += 1
            # we want the ctime
            stored_content_hhashes = content_hex_hashes(
                content_find(stored_content))

            falsy_collisions[hex_hash_id] = [
                ('stored-cnt', stored_content_hhashes),
                ('sentry-cnt', collision_content_hhashes),
                ('difference', diff_hashes)
            ]
        else:
            count_collisions += 1
            collisions[hex_hash_id] = [
                ('stored-cnt', stored_content_hhashes),
                ('sentry-cnt', collision_content_hhashes),
                ('difference', diff_hashes)
            ]

    summary = {
        'total-collisions-raised-in-sentry': count,
        'total-collisions': count_collisions,
        'total-falsy-collisions': count_falsy_collisions,
        'detailed-collisions': collisions,
        'detailed-falsy-collisions': falsy_collisions,
    }

    click.echo(json.dumps(summary))


if __name__ == '__main__':
    main()
