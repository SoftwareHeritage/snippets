#!/usr/bin/python3

import os
import sys
import threading

import psycopg2

from utils import copy_identifiers, DSN


def get_easy_origins(db, type, filename):
    query = """
        COPY (select id, array(
          select url from origin
          where origin.id in (
            select distinct oh.origin
            from occurrence_history oh
            where target = tmp_bytea.id and target_type='%(type)s'
            order by 1)
        )
        from tmp_bytea) TO STDOUT
        """ % {'type': type}
    cur = db.cursor()

    r_fd, w_fd = os.pipe()

    def thread():
        copy_identifiers(cur, filename)
        with open(w_fd, 'wb') as w_file:
            cur.copy_expert(query, w_file)

    read_thread = threading.Thread(target=thread)

    read_thread.start()

    with open(r_fd, 'rb') as r_file:
        for line in r_file:
            id, origins = line.decode().strip().split('\t')
            origins = origins[1:-1]
            if origins:
                origins = origins.split(',')
            else:
                origins = []
            yield (id[3:], origins)

    read_thread.join()


if __name__ == '__main__':
    if len(sys.argv) != 3:
        sys.exit(2)

    type, filename = sys.argv[1:]
    db = psycopg2.connect(DSN)
    for id, origins in get_easy_origins(db, type, filename):
        print(id, ' '.join(origins))
    db.rollback()
