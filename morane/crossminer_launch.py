#!/usr/bin/env python3

import click
import csv
import psycopg2
import sys


class DB_connection:
    """Connection to db class.

    """
    def __init__(self, db_conn_string='service=mirror-swh'):
        self.conn = psycopg2.connect(db_conn_string)

    def execute_query(self, query):
        """Connect to swh archive to execute query

        """
        try:
            cursor = self.conn.cursor()
            cursor.execute(query)
            records = cursor.fetchall()
            cursor.close()
            return records
        except psycopg2.DatabaseError as e:
            print('Error ', e)
            sys.exit(1)

    def close_db(self):
        """Close connection

        """
        self.conn.close()

    def records_to_file(self, file_name, records):
        """Print to file with file_name the records in line

        """
        with open(file_name, 'w') as f:
            writer = csv.writer(f, delimiter=' ')
            for row in records:
                writer.writerow(row)


def origin_scan_query(min_batch, max_batch, file_name):
    """Retrieve origins between range [min_batch, max_batch[ whose last
       visit resulted in a revision targetting a directory holding a
       filename matching the pattern `filename`.

    """
    limit = max_batch - min_batch
    return """
        WITH last_visited AS (
               SELECT o.url url, ov.snapshot_id snp, date
           FROM origin o
           INNER JOIN origin_visit ov on o.id = ov.origin
           WHERE %s <= o.id AND
                 o.id < %s AND
                 ov.visit = (select max(visit) FROM origin_visit
                     where origin=o.id)
                 order by o.id limit %s
            ), head_branch_revision AS (
            SELECT lv.url url, s.id snp_sha1, sb.target revision_sha1,
                   lv.date date
            FROM last_visited lv
            INNER JOIN snapshot s on lv.snp = s.object_id
            INNER JOIN snapshot_branches sbs on  s.object_id  = sbs.snapshot_id
            INNER JOIN snapshot_branch sb on sbs.branch_id = sb.object_id
            WHERE sb.name = 'HEAD' AND sb.target_type = 'revision'
              )
        SELECT DISTINCT encode(dir.id, 'hex'), hbr.url url
        FROM head_branch_revision hbr
        INNER JOIN revision rev on hbr.revision_sha1 = rev.id
        INNER JOIN directory dir on rev.directory = dir.id
        INNER JOIN directory_entry_file def on def.id = any(dir.file_entries)
        WHERE def.name='%s'""" % (min_batch, max_batch, limit, file_name)


@click.command()
@click.option('--database', default='service=swh-mirror', required=1,
              help='Connection string to db.')
@click.option('--pattern-filename', default='pom.xml',
              help='Pattern to look for')
@click.option('--start-from', type=click.INT, default=0,
              help="Origin's id range to look for data, and then continues")
@click.option('--block-size', type=click.INT, default=10000,
              help='Default number of origin to lookup')
def main(database, pattern_filename, start_from, block_size):
    """Filter out origins whose last visit resulted in a revision
       targetting a directory holding a filename matching the pattern
       `filename`.

    """
    db = DB_connection(database)
    min_batch = start_from
    max_batch = min_batch + block_size
    while True:
        query = origin_scan_query(min_batch, max_batch, pattern_filename)
        records = db.execute_query(query)
        if not records:
            break
        name = "%s_%s_origin.csv" % (min_batch, max_batch)
        db.records_to_file(name, records)
        print("""Done with batch: %s to %s""" % (min_batch, max_batch))
        min_batch = max_batch
        max_batch += block_size
    db.close_db()


if __name__ == "__main__":
    main()
