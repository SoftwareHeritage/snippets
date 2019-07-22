#!/usr/bin/env python3

import boto3
import botocore.exceptions
import sys
import textwrap
import time

from tables import TABLES

OUTPUT_LOCATION = 's3://softwareheritage/queries/'


def create_database(database_name):
    return 'CREATE DATABASE IF NOT EXISTS {};'.format(database_name)


def drop_table(table):
    return 'DROP TABLE IF EXISTS swh.{};'.format(table['name'])


def create_table(table):
    l = ['CREATE EXTERNAL TABLE IF NOT EXISTS swh.{} ('.format(table['name'])]
    for i, (column_name, column_type) in enumerate(table['columns']):
        l.append('  `{}` {}{}'.format(
            column_name, column_type.upper(),
            ',' if i < len(table['columns']) - 1 else ''))
    l.append(')')
    l.append('STORED AS PARQUET')
    l.append("LOCATION 's3://softwareheritage/graph/{}/'"
             .format(table['name']))
    l.append('TBLPROPERTIES ("parquet.compress"="SNAPPY");')
    return '\n'.join(l)


def repair_table(table):
    return 'MSCK REPAIR TABLE {};'.format(table['name'])


def query(client, query_string, *, desc='Querying', delay_secs=0.5):
    print(desc, end='...', flush=True)
    try:
        res = client.start_query_execution(
            QueryString=query_string,
            ResultConfiguration={'OutputLocation': OUTPUT_LOCATION}
        )
    except botocore.exceptions.ClientError as e:
        raise RuntimeError(str(e) + '\n\nQuery:\n'
                           + textwrap.indent(query_string, ' ' * 2))
    qid = res['QueryExecutionId']
    while True:
        time.sleep(delay_secs)
        print('.', end='', flush=True)
        execution = client.get_query_execution(QueryExecutionId=qid)
        status = execution['QueryExecution']['Status']
        if status['State'] in ('SUCCEEDED', 'FAILED', 'CANCELLED'):
            break
    print(' {}.'.format(status['State']), flush=True)
    if status['State'] != 'SUCCEEDED':
        raise RuntimeError(status['StateChangeReason'] + '\n\nQuery:\n'
                           + textwrap.indent(query_string, ' ' * 2))


def query(client, query_string, **kwargs):
    print(query_string)


def main():
    client = boto3.client('athena')
    query(client, create_database('swh'), desc='Creating swh database')
    if len(sys.argv) >= 2 and sys.argv[1] == '--replace-tables':
        for table in TABLES:
            query(client, drop_table(table),
                  desc='Dropping table {}'.format(table['name']))
    for table in TABLES:
        query(client, create_table(table),
              desc='Creating table {}'.format(table['name']))
    for table in TABLES:
        query(client, repair_table(table),
              desc='Refreshing table metadata for {}'.format(table['name']))


if __name__ == '__main__':
    main()
