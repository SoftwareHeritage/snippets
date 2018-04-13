#!/usr/bin/env python3
import sys
import psycopg2
import time
from collections import OrderedDict
import csv

class DB_connection:

	def __init__(self):
		self.conn = psycopg2.connect(dbname='softwareheritage',
									 host= 'somerset.internal.softwareheritage.org',
									 user='guest',
									 password='guest',
									 port=5433)


	def execute_query(self, query):
		"""
		connects to swh archive and executes query in args
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
		self.conn.close()

	def records_to_file(self, file_name, records):
		"""
		prints to file with file_name the records in line
		"""
		with open(file_name, 'w') as f:
			writer = csv.writer(f, delimiter=' ')
			for row in records:
				writer.writerow(row)


def origin_scan(min_batch, max_batch, file_name):
		return """
	 	WITH last_visited AS (
		       SELECT o.url url, ov.snapshot_id snp, date
        	   FROM origin o
               INNER JOIN origin_visit ov on o.id = ov.origin
        	   WHERE 0 <= o.id AND
                     o.id < 1000 AND
                     ov.visit = (select max(visit) FROM origin_visit
                                 where origin=o.id)
                order by o.id limit 10000;
		     ), head_branch_revision AS (
		        SELECT lv.url url, s.id snp_sha1, sb.target revision_sha1, lv.date date
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
		WHERE def.name='%s'"""% (min_batch, max_batch, file_name)


def main():
	db = DB_connection()
	min_batch = 410000
	max_batch = 420000
	file_name = "pom.xml"
	while max_batch < 83800178:
		records = db.execute_query(origin_scan(min_batch, max_batch, file_name))
		name = "%s_%s_origin.csv" % (min_batch, max_batch)
		db.records_to_file(name, records)
		print("""Done with batch: %s to %s"""% (min_batch, max_batch))
		min_batch = max_batch
		max_batch = min_batch + 10000
	db.close_db()

if __name__ == "__main__":
	main()
