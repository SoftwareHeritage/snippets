#!/usr/bin/python3

import pprint
import sys

import psycopg2

from swh.storage import converters
from swh.model import identifiers

from utils import DSN, RELEASE_COLUMNS, process_query, copy_identifiers

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


def releases_from_file(cursor, filename):
    copy_identifiers(cursor, filename)
    yield from process_query(cursor, RELEASE_QUERY, RELEASE_COLUMNS,
                             converters.db_to_release)


if __name__ == '__main__':
    db = psycopg2.connect(DSN)
    cursor = db.cursor()
    for release in releases_from_file(cursor, sys.argv[1]):
        intrinsic_id = id_to_str(release['id'])
        computed_id = id_to_str(identifiers.release_identifier(release))
        if computed_id != intrinsic_id:
            print(intrinsic_id)
        else:
            pprint.pprint(release, stream=sys.stderr)
