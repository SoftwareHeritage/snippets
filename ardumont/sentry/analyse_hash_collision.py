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
from typing import Any, Dict, List, Tuple

import click

from swh.model.hashutil import hash_to_hex, DEFAULT_ALGORITHMS


def import_data(f):
    return json.loads(open(f).read())


def content_get_metadata(
        content_ids: List[bytes]) -> Dict[bytes, Dict[str, Any]]:
    """Retrieve contents from the storage

    """
    from swh.storage import get_storage
    storage = get_storage(
        cls='remote', url='http://uffizi.internal.softwareheritage.org:5002')
    contents = storage.content_get_metadata(content_ids)
    result = {}
    for hash_id, all_contents in contents.items():
        count = len(all_contents)
        if count > 1:
            click.echo(f'hash_id {hash_id} has multiple entries: {count}')
        # to ease comparison:
        # - take only 1 of the contents (most cases i guess)
        # - drop the length
        hashes = all_contents[0]
        hashes.pop('length', None)
        result[hash_id] = hashes

    return result


def content_hex_hashes(content: Dict[str, bytes]) -> Dict[str, str]:
    """Convert bytes hashes into hex hashes. Also "enforce" the key order (not an
    OrderedDict though but that seems enough for json dumps).

    """
    return {
        algo: hash_to_hex(content[algo]) for algo in DEFAULT_ALGORITHMS
    }


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

        msg: Tuple[str, bytes, Dict[str, bytes]] = ast.literal_eval(message)
        algo, hash_id, colliding_contents = msg
        # Asserting we only have sha1 collisions so far
        assert algo == 'sha1'

        summary_count[hash_id] += 1

        # take only 1 content, on previous iteration, the list was multiple
        # occurences of the same hash
        # TODO: ensure it remains true
        detailed_collisions[hash_id] = colliding_contents[0]

    # Retrieve the contents from storage to compare
    full_contents = content_get_metadata(list(summary_count.keys()))

    count_collisions = 0
    count_falsy_collisions = 0
    collisions = {}
    falsy_collisions = {}
    for hash_id, stored_content in full_contents.items():
        collision_content = content_hex_hashes(detailed_collisions[hash_id])
        stored_content = content_hex_hashes(stored_content)

        if collision_content != stored_content:
            falsy, diff_hashes = compute_diff_hashes(
                stored_content, collision_content)
            hex_hash_id = hash_to_hex(hash_id)
            if falsy:
                count_falsy_collisions += 1
                falsy_collisions[hex_hash_id] = [
                    ('stored-cnt', stored_content),
                    ('sentry-cnt', collision_content),
                    ('difference', diff_hashes)
                ]
            else:
                count_collisions += 1
                collisions[hex_hash_id] = [
                    ('stored-cnt', stored_content),
                    ('sentry-cnt', collision_content),
                    ('difference', diff_hashes)
                ]

    summary = {
        'total-collisions-raises-in-sentry': count,
        'total-collisions-on-sha1': count_collisions,
        'total-falsy-collisions-on-sha1': count_falsy_collisions,
        'detailed-collisions': collisions,
        'detailed-falsy-collision': falsy_collisions,
    }

    click.echo(json.dumps(summary))


if __name__ == '__main__':
    main()
