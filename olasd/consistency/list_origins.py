#!/usr/bin/python3

import psycopg2

from utils import copy_identifiers, DSN


def process_data(db, type):
    query = {
        'release': """
        select id, array(
          select url from origin
          where origin.id in (
            select distinct oh.origin
            from occurrence_history oh
            where target = tmp_bytea.id and target_type='release'
            order by 1)
        )
        from tmp_bytea
        """,
    }.get(type)
    filename = "broken_%ss" % type
    cur = db.cursor()
    copy_identifiers(cur, filename)
    cur.execute(query)
    for id, origins in cur.fetchall():
        print(bytes(id).hex(), ' '.join(origins))


if __name__ == '__main__':
    db = psycopg2.connect(DSN)
    process_data(db, 'release')
    db.rollback()
