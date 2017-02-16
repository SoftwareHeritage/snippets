#!/usr/bin/python3

import pprint
import sys

import psycopg2

from swh.storage import converters
from swh.model import identifiers

from utils import DSN, RELEASE_COLUMNS, REVISION_COLUMNS, process_query, copy_identifiers

id_to_str = identifiers.identifier_to_str

RELEASE_QUERY = '''
copy (
    select %s
    from tmp_bytea t
    left join release r on t.id = r.id
    left join person a on r.author = a.id
) to stdout
''' % ', '.join('%s as %s' % (column, alias)
                for column, alias, _ in RELEASE_COLUMNS)

REVISION_QUERY = '''
copy (
    select %s
    from tmp_bytea t
    left join revision r on t.id = r.id
    left join person a on r.author = a.id
    left join person c on r.committer = c.id
) to stdout
''' % ', '.join('%s as %s' % (column, alias)
                for column, alias, _ in REVISION_COLUMNS)


def releases_from_file(cursor, filename):
    copy_identifiers(cursor, filename)
    yield from process_query(cursor, RELEASE_QUERY, RELEASE_COLUMNS,
                             converters.db_to_release)


def revisions_from_file(cursor, filename):
    copy_identifiers(cursor, filename)
    yield from process_query(cursor, REVISION_QUERY, REVISION_COLUMNS,
                             converters.db_to_revision)


if __name__ == '__main__':
    if len(sys.argv) != 3:
        sys.exit(2)

    if sys.argv[1] == 'release':
        iterator = releases_from_file
        identifier_fn = identifiers.release_identifier
    elif sys.argv[1] == 'revision':
        iterator = revisions_from_file
        identifier_fn = identifiers.revision_identifier
    else:
        sys.exit(2)

    db = psycopg2.connect(DSN)
    cursor = db.cursor()
    for object in iterator(cursor, sys.argv[2]):
        intrinsic_id = id_to_str(object['id'])
        computed_id = id_to_str(identifier_fn(object))
        if computed_id != intrinsic_id:
            print(intrinsic_id)
