#!/usr/bin/env python3

# Copyright (C) 2021  The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information

import functools

import psycopg2
import psycopg2.extras

from swh.journal.client import get_journal_client


def process_journal_objects(messages, *, conn):
    assert set(messages) == {"revision"}, set(messages)
    revisions = messages["revision"]

    rows = []
    for revision in revisions:
        if revision.get("extra_headers"):
            rows.append((revision["id"], revision["extra_headers"]))

    cur = conn.cursor()
    psycopg2.extras.execute_values(
        cur,
        """
        UPDATE revision
        SET extra_headers = data.extra_headers
        FROM (VALUES %s) AS data (id, extra_headers)
        WHERE
            revision.id=data.id
            AND (
                -- Don't unnecessarily update rows that already have their
                -- 'extra_headers' cell populated
                revision.extra_headers = ARRAY[]::bytea[]
                OR revision.extra_headers IS NULL
            )
        """,
        rows,
    )

    print(f"processed {len(rows)} revisions")


def main():
    client = get_journal_client(
        cls="kafka",
        prefix="swh.journal.objects",
        object_types=["revision"],
        brokers=[f"kafka{i+1}.internal.softwareheritage.org:9092" for i in range(4)],
        group_id="vlorentz-T2564-migrate-extra-headers",
    )
    conn = psycopg2.connect("service=swh")

    worker_fn = functools.partial(process_journal_objects, conn=conn)

    client.process(worker_fn)


if __name__ == "__main__":
    main()
