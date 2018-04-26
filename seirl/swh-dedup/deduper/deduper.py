import magic
import psycopg2
import random
import time
import zlib

from psycopg2.extras import execute_values, RealDictCursor

from swh.objstorage import PathSlicingObjStorage as ObjStorage
from deduper.chunkers import chunk

class Deduper:
    def __init__(self, db_service, objs_root, objs_slicing):
        self.db_conn = psycopg2.connect('service=%s' % db_service)
        self.db_conn.autocommit = True
        self.obj_storage = ObjStorage(objs_root, objs_slicing)

    def dedup(self, content_id):
        content = self.obj_storage.get(content_id)
        self._insert_content(content_id, content)

        # get list of methods not yet sweeped
        with self.db_conn.cursor(cursor_factory=RealDictCursor) as c:
            c.execute("""SELECT id, algo, min_block_size, average_block_size,
                                max_block_size, window_size
                      FROM chunking_method
                      WHERE NOT EXISTS (
                        SELECT 1 FROM chunked_content
                        WHERE content_id = %s
                      )""",
                      (content_id,))
            methods = list(c.fetchall())

        random.shuffle(methods)
        _ = max(content) # Force read and cache content  # noqa

        chunked_content_queue = []
        for method in methods:
            method_id = method['id']
            algo = method['algo']
            params = {
                'min_block_size': method['min_block_size'],
                'average_block_size': method['average_block_size'],
                'max_block_size': method['max_block_size'],
                'window_size': method['window_size'],
            }
            t0 = int(time.monotonic() * 1000000)
            chunks = list(chunk(algo, params, content))
            t = int(time.monotonic() * 1000000)
            duration = t - t0

            chunked_content_queue.append(
                (content_id, method_id, duration, chunks))
        self._insert_chunks(chunked_content_queue)

    def _insert_content(self, content_id, content):
        size = len(content)
        compressed_size = len(zlib.compress(content))
        try:
            ftype = magic.from_buffer(content)
        except:
            ftype = ''

        with self.db_conn.cursor() as cur:
            cur.execute("""INSERT INTO content
                                (id, length, compressed_length, file_type)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT DO NOTHING""",
                        (content_id, size, compressed_size, ftype))

    def _insert_chunks(self, chunked_content_queue):
        chunked_content_values = []
        for content_id, method_id, duration, chunks in chunked_content_queue:
            chunked_content_values.append((content_id, method_id, duration))

        with self.db_conn.cursor() as cur:
            execute_values(cur, """INSERT INTO chunked_content
                                    (content_id, method_id, duration_us)
                                VALUES %s
                           RETURNING id, content_id, method_id""",
                           chunked_content_values)
            chunked_content_ids = {
                (bytes(content_id), method_id): id
                for id, content_id, method_id in cur.fetchall()
            }

            chunk_values = []
            chunked_content_chunks_values = []
            for content_id, method_id, _, chunks in chunked_content_queue:
                for (chunk_id, position, length, compressed_length) in chunks:
                    chunk_values.append((chunk_id, length, compressed_length))
                    chunked_content_id = chunked_content_ids[
                        (content_id, method_id)]
                    chunked_content_chunks_values.append(
                        (chunked_content_id, chunk_id, position))

            execute_values(cur, """INSERT INTO chunk
                                    (id, length, compressed_length)
                                VALUES %s
                                ON CONFLICT DO NOTHING""",
                           chunk_values)
            execute_values(cur, """INSERT INTO chunked_content_chunk
                                    (chunked_content_id, chunk_id, position)
                                VALUES %s""",
                           chunked_content_chunks_values)
