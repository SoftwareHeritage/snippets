#!/usr/bin/python3

"""compute Rabin fingerprints of Software Heritage content objects

Read a list of Software Heritage content object IDs on standard input, fetch
each of them from a (local) object storage and apply Rabin fingerprinting to
its content. Store in a (postgres) DB the mapping between content objects and
(Rabin-delimited) chunks.

"""

import magic
import psycopg2
import zlib

from psycopg2.extras import execute_values, RealDictCursor

from swh.objstorage import PathSlicingObjStorage as ObjStorage
from deduper.chunkers import chunk

OBJS_ROOT = '/srv/softwareheritage/objects'
OBJS_SLICING = '0:2/2:4'
DB_SERVICE = 'swh-dedup'  # postgres service name


class Deduper:
    def __init__(self):
        self.db_conn = psycopg2.connect('service=%s' % DB_SERVICE)
        self.obj_storage = ObjStorage(OBJS_ROOT, OBJS_SLICING)

    def dedup(self, content_id):
        content = self.obj_storage.get(content_id)
        self._insert_content(content_id, content)

        # get list of methods not yet sweeped
        with self.db_conn.cursor(cursor_factory=RealDictCursor) as c:
            c.execute("""SELECT id, algo, min_block_size, average_block_size,
                                max_block_size, window_size
                      FROM chunking_method
                      LEFT JOIN chunked_content
                      ON method_id = chunking_method.id
                      WHERE content_id = %s AND method_id IS NULL""",
                      (content_id,))
            methods = c.fetchall()

        for method in methods:
            method_id = method['id']
            algo = method['algo']
            params = {
                'min_block_size': method['min_block_size'],
                'average_block_size': method['average_block_size'],
                'max_block_size': method['max_block_size'],
                'window_size': method['window_size'],
            }
            chunks = list(chunk(algo, params, content))
            self._insert_chunks(content_id, method_id, chunks)

    def _insert_content(self, content_id, content):
        size = len(content)
        compressed_size = len(zlib.compress(content))
        ftype = magic.from_buffer(content)

        with self.db_conn.cursor() as cur:
            cur.execute("""INSERT INTO content
                                (id, length, compressed_length, file_type)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT DO NOTHING""",
                        (content_id, size, compressed_size, ftype))

    def _insert_chunks(self, content_id, method_id, chunks):
        chunk_values = []
        chunked_content_values = []
        for (chunk_id, position, length, compressed_length) in chunks:
            chunk_values.append((chunk_id, length, compressed_length))
            chunked_content_values.append((content_id, chunk_id, method_id,
                                           position))
        with self.db_conn.cursor() as cur:
            execute_values(cur, """INSERT INTO chunk
                                    (id, length, compressed_length)
                                VALUES %s
                                ON CONFLICT DO NOTHING""",
                           chunk_values)
            execute_values(cur, """INSERT INTO chunked_content
                                    (content_id, chunk_id, method_id, position)
                                VALUES %s""",
                           chunked_content_values)