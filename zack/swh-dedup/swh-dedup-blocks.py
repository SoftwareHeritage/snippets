#!/usr/bin/python3

"""compute Rabin fingerprints of Software Heritage content objects

Read a list of Software Heritage content object IDs on standard input, fetch
each of them from a (local) object storage and apply Rabin fingerprinting to
its content. Store in a (postgres) DB the mapping between content objects and
(Rabin-delimited) chunks.

"""

import logging
import psycopg2
import rabin
import sys

from hashlib import sha1
from psycopg2.extras import execute_values

from swh.model.hashutil import hash_to_bytes
from swh.objstorage import PathSlicingObjStorage as ObjStorage
from swh.objstorage.exc import ObjNotFoundError

OBJS_ROOT = '/srv/softwareheritage/objects'
OBJS_SLICING = '0:2/2:4'
DB_SERVICE = 'swh-dedup'  # postgres service name
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


def db_insert_chunks(db_conn, content_id, length, chunks):
    with db_conn.cursor() as cur:
        cur.execute('INSERT INTO content (id, length) VALUES (%s, %s)',
                    (content_id, length))

        chunk_values = []
        chunked_content_values = []
        for (chunk_id, position, length) in chunks:
            chunk_values.append((chunk_id, length))
            chunked_content_values.append((content_id, chunk_id, position))

        execute_values(cur, '''INSERT INTO chunk (id, length) VALUES %s
                               ON CONFLICT DO NOTHING''',
                       chunk_values)
        execute_values(cur, '''INSERT INTO chunked_content
                               (content_id, chunk_id, position) VALUES %s''',
                       chunked_content_values)


def print_summary(db_conn):
    with db_conn.cursor() as c:
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


def dedup(db_conn, content_id, content):
    with db_conn.cursor() as c:  # skip deduplication if content is known
        c.execute('SELECT 1 FROM content WHERE id = %s', [content_id])
        if c.fetchone():
            return

    # do Rabin fingerprinting
    r = rabin.Rabin()
    buf = bytearray()
    for data in content:
        buf.extend(data)  # TODO avoid loading the entire content in memory
        r.update(data)

    with db_conn:  # transaction
        chunks = []
        if buf:  # r.fingerprints() invoked on empty objects segfaults :-(
            for (position, length, _fpr) in r.fingerprints():
                chunk = buf[position:(position+length)]
                chunk_id = sha1(chunk).digest()
                chunks.append((chunk_id, position, length))

        db_insert_chunks(db_conn, content_id, len(buf), chunks)

    r.clear()


def main():
    rabin_init(RABIN_PARAMS)
    objs = ObjStorage(OBJS_ROOT, OBJS_SLICING)
    db_conn = psycopg2.connect('service=%s' % DB_SERVICE)

    obj_count = 0
    for line in sys.stdin:
        content_id = line.rstrip()
        # print('object', content_id)
        try:
            dedup(db_conn, hash_to_bytes(content_id),
                  objs.get_stream(content_id))
        except ObjNotFoundError:
            logging.warning('cannot find object "%s", skipping' % content_id)

        obj_count += 1
        if obj_count % 1000 == 0:
            logging.info('processed %d objects, currently at %s' %
                         (obj_count, content_id))

    print_summary(db_conn)


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    main()
