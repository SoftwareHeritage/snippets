#!/usr/bin/env python3

import psycopg2

from swh.storage import converters as db_converters
from swh.model import identifiers

from utils import DSN, REVISION_COLUMNS, RELEASE_COLUMNS, process_query

id_to_str = identifiers.identifier_to_str

REVISION_QUERY = '''
copy (
    select %s
    from revision r
    left join person a on r.author = a.id
    left join person c on r.committer = c.id
) to stdout
''' % ', '.join('%s as %s' % (column, alias)
                for column, alias, _ in REVISION_COLUMNS)

RELEASE_QUERY = '''
copy (
    select %s
    from release r
    left join person a on r.author = a.id
) to stdout
''' % ', '.join('%s as %s' % (column, alias)
                for column, alias, _ in RELEASE_COLUMNS)


if __name__ == '__main__':
    db = psycopg2.connect(DSN)
    cursor = db.cursor()

    with open('broken_releases', 'w') as broken_releases:
        for release in process_query(cursor, RELEASE_QUERY, RELEASE_COLUMNS,
                                     db_converters.db_to_release):
            intrinsic_id = id_to_str(release['id'])
            computed_id = id_to_str(identifiers.release_identifier(release))
            if intrinsic_id != computed_id:
                print(intrinsic_id, computed_id, file=broken_releases)

    with open('broken_revisions', 'w') as broken_revisions:
        for revision in process_query(cursor, REVISION_QUERY, REVISION_COLUMNS,
                                      db_converters.db_to_revision):
            intrinsic_id = id_to_str(revision['id'])
            computed_id = id_to_str(identifiers.revision_identifier(revision))
            if intrinsic_id != computed_id:
                print(intrinsic_id, computed_id, file=broken_revisions)

    db.rollback()
