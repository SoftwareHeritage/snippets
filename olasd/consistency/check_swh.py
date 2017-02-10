#!/usr/bin/python3

import os
import threading

import psycopg2

import converters
from swh.storage import converters as db_converters
from swh.model import identifiers

id_to_str = identifiers.identifier_to_str

DSN = ('host=somerset.internal.softwareheritage.org port=5433 '
       'user=guest dbname=softwareheritage')

REVISION_COLUMNS = [
    ("r.id", "id", converters.tobytes),
    ("date", "date", converters.todate),
    ("date_offset", "date_offset", converters.toint),
    ("committer_date", "committer_date", converters.todate),
    ("committer_date_offset", "committer_date_offset", converters.toint),
    ("type", "type", converters.tostr),
    ("directory", "directory", converters.tobytes),
    ("message", "message", converters.tobytes),
    ("synthetic", "synthetic", converters.tobool),
    ("metadata", "metadata", converters.tojson),
    ("date_neg_utc_offset", "date_neg_utc_offset", converters.tobool),
    ("committer_date_neg_utc_offset", "committer_date_neg_utc_offset",
     converters.tobool),
    ("array(select parent_id::bytea from revision_history rh "
     "where rh.id = r.id order by rh.parent_rank asc)",
     "parents", converters.tolist),
    ("a.id", "author_id", converters.toint),
    ("a.name", "author_name", converters.tobytes),
    ("a.email", "author_email", converters.tobytes),
    ("a.fullname", "author_fullname", converters.tobytes),
    ("c.id", "committer_id", converters.toint),
    ("c.name", "committer_name", converters.tobytes),
    ("c.email", "committer_email", converters.tobytes),
    ("c.fullname", "committer_fullname", converters.tobytes),
]

REVISION_QUERY = '''
copy (
    select %s
    from revision r
    left join person a on r.author = a.id
    left join person c on r.committer = c.id
) to stdout
''' % ', '.join('%s as %s' % (column, alias)
                for column, alias, _ in REVISION_COLUMNS)

RELEASE_COLUMNS = [
    ("r.id", "id", converters.tobytes),
    ("date", "date", converters.todate),
    ("date_offset", "date_offset", converters.toint),
    ("comment", "comment", converters.tobytes),
    ("r.name", "name", converters.tobytes),
    ("synthetic", "synthetic", converters.tobool),
    ("date_neg_utc_offset", "date_neg_utc_offset", converters.tobool),
    ("target", "target", converters.tobytes),
    ("target_type", "target_type", converters.tostr),
    ("a.id", "author_id", converters.toint),
    ("a.name", "author_name", converters.tobytes),
    ("a.email", "author_email", converters.tobytes),
    ("a.fullname", "author_fullname", converters.tobytes),
]

RELEASE_QUERY = '''
copy (
    select %s
    from release r
    left join person a on r.author = a.id
) to stdout
''' % ', '.join('%s as %s' % (column, alias)
                for column, alias, _ in RELEASE_COLUMNS)


def process_query(query, columns, db_converter):
    r_fd, w_fd = os.pipe()
    db = psycopg2.connect(DSN)

    def get_data_thread():
        cursor = db.cursor()
        cursor.copy_expert(query, open(w_fd, 'wb'))
        cursor.close()
        db.commit()

    data_thread = threading.Thread(target=get_data_thread)
    data_thread.start()

    r = open(r_fd, 'rb')
    for line in r:
        fields = {
            alias: decoder(value)
            for (_, alias, decoder), value
            in zip(columns, line[:-1].decode('utf-8').split('\t'))
        }
        yield db_converter(fields)

    r.close()

    data_thread.join()


if __name__ == '__main__':
    with open('broken_releases', 'w') as broken_releases:
        for release in process_query(RELEASE_QUERY, RELEASE_COLUMNS,
                                     db_converters.db_to_release):
            intrinsic_id = id_to_str(release['id'])
            computed_id = id_to_str(identifiers.release_identifier(release))
            if intrinsic_id != computed_id:
                print(intrinsic_id, computed_id, file=broken_releases)

    with open('broken_revisions', 'w') as broken_revisions:
        for revision in process_query(REVISION_QUERY, REVISION_COLUMNS,
                                      db_converters.db_to_revision):
            intrinsic_id = id_to_str(revision['id'])
            computed_id = id_to_str(identifiers.revision_identifier(revision))
            if intrinsic_id != computed_id:
                print(intrinsic_id, computed_id, file=broken_revisions)
