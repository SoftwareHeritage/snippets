#!/usr/bin/python3

"""compute Rabin fingerprints of Software Heritage content objects

Read a list of Software Heritage content object IDs on standard input, fetch
each of them from a (local) object storage and apply Rabin fingerprinting to
its content. Store in a (sqlite) DB the mapping between content objects and
(Rabin-delimited) chunks.

"""

import logging
import os
import rabin
import sqlite3
import sys

from hashlib import sha1

from swh.objstorage import PathSlicingObjStorage as ObjStorage
from swh.objstorage.exc import ObjNotFoundError

OBJS_ROOT = '/srv/softwareheritage/objects'
OBJS_SLICING = '0:2/2:4'
SQLITE_DB = 'swh-dedup.db'
RABIN_PARAMS = {
    # 'prime': 3,
    # 'window_size': 48,  # bytes
    # 'min_block_size':  2 * 1024,  # bytes
    # 'avg_block_size':  8 * 1024,  # bytes
    # 'max_block_size': 64 * 1024,  # bytes
}


def rabin_init(params):
    if 'prime' in params:
        rabin.set_prime(params['prime'])
    if 'window_size' in params:
        rabin.set_window_size(params['window_size'])
    if 'min_block_size' in params:
        rabin.set_min_block_size(params['min_block_size'])
    if 'avg_block_size' in params:
        rabin.set_avg_block_size(params['avg_block_size'])
    if 'max_block_size' in params:
        rabin.set_max_block_size(params['max_block_size'])


def db_init(db):
    with db:
        db.execute('''CREATE TABLE content (
id string PRIMARY KEY,  -- SHA1 checksum
length integer
)''')
        db.execute('''CREATE TABLE chunk (
id string PRIMARY KEY,  -- SHA1 checksum
length integer
)''')
        db.execute('''CREATE TABLE chunked_content (
content_id string REFERENCES content(sha1),
chunk_id string REFERENCES chunk(sha1),
offset integer
)''')
        db.execute('''CREATE INDEX idx_chunked_content_id
ON chunked_content (content_id)
''')


def db_insert_chunk(db, content_id, chunk_id, offset, length):
    with db:
        c = db.cursor()

        c.execute('SELECT 1 FROM chunk WHERE id = ?', [chunk_id])
        if not c.fetchone():
            c.execute('INSERT INTO chunk (id, length) VALUES (?, ?)',
                      (chunk_id, length))

        c.execute('''INSERT INTO chunked_content
                      (content_id, chunk_id, offset) VALUES (?, ?, ?)''',
                  (content_id, chunk_id, offset))


def db_insert_content(db, content_id, length):
    with db:
        c = db.cursor()

        c.execute('SELECT 1 FROM content WHERE id = ?', [content_id])
        if not c.fetchone():
            db.execute('INSERT INTO content (id, length) VALUES (?, ?)',
                       (content_id, length))


def print_summary(db):
    with db:
        c = db.cursor()

        c.execute('SELECT count(*) FROM content')
        print('contents:', c.fetchone()[0])
        c.execute('SELECT count(*) FROM chunk')
        print('chunks:', c.fetchone()[0])

        c.execute('SELECT sum(length) FROM content')
        content_size = int(c.fetchone()[0])
        print('total content size:', content_size)

        c.execute('SELECT sum(length) FROM chunk')
        chunk_size = int(c.fetchone()[0])
        print('total chunk size:', chunk_size)

        print('compression gain: %.2f%%' %
              (100 - float(chunk_size) / content_size * 100))


def dedup(db, oid, content):
    r = rabin.Rabin()
    buf = bytearray()

    for data in content:
        buf.extend(data)  # TODO avoid loading the entire content in memory
        r.update(data)

    if buf:  # r.fingerprints() invoked on empty objects segfaults :-(
        for (offset, length, _fpr) in r.fingerprints():
            chunk = buf[offset:(offset+length)]
            chunk_id = sha1(chunk).hexdigest()
            db_insert_chunk(db, oid, chunk_id, offset, length)

    r.clear()
    return len(buf)


def main():
    rabin_init(RABIN_PARAMS)

    objs = ObjStorage(OBJS_ROOT, OBJS_SLICING)

    missing_db = not os.path.exists(SQLITE_DB)
    db = sqlite3.connect('swh-dedup.db')
    if missing_db:
        db_init(db)

    obj_count = 0
    for line in sys.stdin:
        oid = line.rstrip()
        # print('object', oid)
        try:
            object_len = dedup(db, oid, objs.get_stream(oid))
            db_insert_content(db, oid, object_len)
        except ObjNotFoundError:
            logging.warning('cannot find object "%s", skipping' % oid)

        obj_count += 1
        if obj_count % 1000 == 0:
            logging.info('processed %d objects, currently at %s' %
                         (obj_count, oid))

    print_summary(db)


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    main()
