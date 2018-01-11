#!/usr/bin/python3

from ast import literal_eval
from collections import defaultdict
import csv
import os
import psycopg2
import sys
import threading

from swh.model.identifiers import snapshot_identifier, identifier_to_bytes
from swh.storage.storage import Storage

read_storage = None
write_storage = None

GET_OCCURRENCES_QUERY = '''COPY (
    select origin, branch, target, target_type, visits from occurrence_history
    where origin >= %s
    order by origin, branch
) TO STDOUT CSV
'''

DSN_READ = 'service=swh-s'
DSN_WRITE = 'service=swh-swhstorage'


def get_read_storage():
    global read_storage
    if not read_storage:
        read_storage = Storage(DSN_READ, {
            'cls': 'in-memory',
            'args': {},
        })
    return read_storage


def get_write_storage():
    global write_storage
    if not write_storage:
        write_storage = Storage(DSN_WRITE, {
            'cls': 'in-memory',
            'args': {},
        })
    return write_storage


def get_snapshots(origin):
    read_fd, write_fd = os.pipe()

    def get_data_thread():
        db = psycopg2.connect(DSN_READ)
        cursor = db.cursor()
        cursor.copy_expert(
            cursor.mogrify(GET_OCCURRENCES_QUERY, (origin, )),
            open(write_fd, 'wb')
        )
        cursor.close()
        db.close()

    data_thread = threading.Thread(target=get_data_thread)
    data_thread.start()

    snapshots = defaultdict(lambda: defaultdict(lambda: {'branches': {}}))

    current_origin = None

    for line in csv.reader(open(read_fd, 'r')):
        origin, branch, target, target_type, visits = line
        branch = bytes.fromhex(branch[2:])
        target = bytes.fromhex(target[2:])
        visits = literal_eval(visits)
        for visit in visits:
            snapshots[origin][visit]['branches'][branch] = {
                'target': target,
                'target_type': target_type,
            }

        if current_origin and origin != current_origin:
            # done processing the current origin; send snapshots
            for visit, snapshot in sorted(snapshots[current_origin].items()):
                for branch, target in snapshot['branches'].copy().items():
                    if target == {
                        'target': b'\x00' * 20,
                        'target_type': 'revision',
                    }:
                        snapshot['branches'][branch] = None
                snapshot_id = snapshot_identifier(snapshot)
                snapshot['id'] = identifier_to_bytes(snapshot_id)
                yield current_origin, visit, snapshot
            del snapshots[current_origin]

        current_origin = origin

    data_thread.join()


if __name__ == '__main__':
    get_read_storage()
    get_write_storage()

    min_origin = 0

    if len(sys.argv) >= 2:
        min_origin = int(sys.argv[1])

    current_origin = None
    cursor = None
    for origin, visit, snapshot in get_snapshots(min_origin):
        if origin != current_origin and cursor:
            write_storage.db.conn.commit()
            cursor = None

        current_origin = origin

        if not cursor:
            cursor = write_storage.db.conn.cursor()

        cursor.execute("""\
        select snapshot_id from origin_visit
        where origin=%s and visit=%s
              and status in ('full', 'partial')""",
                       (origin, visit))

        data = cursor.fetchone()
        if not data:
            print('origin_visit', origin, visit, 'not found')
            continue
        if not data[0]:
            write_storage.snapshot_add(origin, visit, snapshot,
                                       back_compat=False, cur=cursor)
            cursor.execute('drop table tmp_snapshot_branch')
            print('origin_visit', origin, visit, 'ok')
        elif data[0] != snapshot['id']:
            print('origin_visit', origin, visit, 'discrepancy: db has',
                  data[0], 'computed', snapshot['id'])
            continue
        else:
            continue
