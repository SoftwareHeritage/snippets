#!/usr/bin/python3

import os
import psycopg2
import sys
import threading

from swh.model.identifiers import snapshot_identifier, identifier_to_bytes
from swh.storage.storage import Storage

read_storage = None
write_storage = None

GET_VISITS_QUERY = '''
copy (
    select origin, visit
    from origin_visit ov
    where snapshot_id is null
    and status in ('full', 'partial')
    and (origin, visit) >= (%s, %s)
    order by origin, visit
) to stdout'''

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


def get_visits(min_origin=0, min_visit=0):
    read_fd, write_fd = os.pipe()

    def get_data_thread():
        db = psycopg2.connect(DSN_READ)
        cursor = db.cursor()
        cursor.copy_expert(
            cursor.mogrify(GET_VISITS_QUERY, (min_origin, min_visit)),
            open(write_fd, 'wb')
        )
        cursor.close()
        db.close()

    data_thread = threading.Thread(target=get_data_thread)
    data_thread.start()

    for line in open(read_fd, 'r'):
        origin, visit = line.strip().split()
        yield (int(origin), int(visit))

    data_thread.join()


if __name__ == '__main__':
    get_read_storage()
    get_write_storage()

    min_origin = min_visit = 0

    if len(sys.argv) >= 2:
        min_origin = int(sys.argv[1])

    if len(sys.argv) >= 3:
        min_visit = int(sys.argv[2])

    for origin, visit in get_visits(min_origin, min_visit):
        snapshot = read_storage.snapshot_get_by_origin_visit(origin, visit)
        for branch, target in snapshot['branches'].copy().items():
            if target == {'target': b'\x00' * 20, 'target_type': 'revision'}:
                snapshot['branches'][branch] = None
        snapshot_id = snapshot_identifier(snapshot)
        snapshot['id'] = identifier_to_bytes(snapshot_id)
        print(origin, visit, snapshot_id)
        write_storage.snapshot_add(origin, visit, snapshot, back_compat=False)
