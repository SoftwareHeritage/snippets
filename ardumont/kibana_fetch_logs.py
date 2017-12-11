#!/usr/bin/env python3
# Use:
# ./kibana_fetch_logs.py | tee temporary-error-file

# Copyright (C) 2017 the Software Heritage developers
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information

import ast
import click
import requests


PAYLOAD_REQUESTS = {
  "from": 0,
  "_source": [
    "message",
    "swh_logging_args_args",
    "swh_logging_args_exc",
    "swh_logging_args_kwargs"
  ],
  "sort": [
    {
      "@timestamp": "asc"
    }
  ],
  "query": {
    "bool": {
      "must": [
        {
          "match": {
            "systemd_unit": {
              "query": "swh-worker@swh_loader_svn.service",
              "type": "phrase"
            }
          }
        },
        {
          "term": {
            "priority": "3"
          }
        }
      ],
      "must_not": [
        {
          "match": {
            "message": {
              "query": "[.*] Uneventful visit. Detail: file",
              "type": "phrase"
            }
          }
        },
        {
          "match": {
            "message": {
              "query": ".*Failed to mount the svn dump.*",
              "type": "phrase"
            }
          }
        },
        {
          "match": {
            "message": {
              "query": "[.*] Loading failure, updating to `partial`",
              "type": "phrase"
            }
          }
        },
        {
          "match": {
            "message": {
              "query": "[.*] consumer: Cannot connect to amqp.*",
              "type": "phrase"
            }
          }
        },
        {
          "match": {
            "message": {
              "query": "[.*] pidbox command error.*",
              "type": "phrase"
            }
          }
        }
      ]
    }
  }
}


def retrieve_data(server, indexes, types, size, start=None):
    """Retrieve information from server looking up through 'indexes' and
    'types'.  This returns result of length 'size' starting from the
    'start' position.

    """
    payload = PAYLOAD_REQUESTS.copy()
    payload['size'] = size
    if start:
        payload['search_after'] = [start]

    url = '%s/%s/%s/_search' % (server, indexes, types)

    r = requests.post(url, json=payload)
    if r.ok:
        return r.json()


def format_result(json):
    """Format result from the server's response"""
    if not json:
        return {}

    hits = json.get('hits')
    if not hits:
        return {}

    total_hits = hits.get('total')
    if not total_hits:
        return {}

    hits = hits.get('hits')
    if not hits:
        return {}

    all_data = []
    last_sort_time = None
    for data in hits:
        last_sort_time = data['sort'][0]
        source = data['_source']
        _data = {}

        swh_logging_args_args = source.get('swh_logging_args_args')
        if swh_logging_args_args:
            _data['args'] = ast.literal_eval(swh_logging_args_args)

        swh_logging_args_kwargs = source.get('swh_logging_args_kwargs')
        if swh_logging_args_kwargs:
            _data['kwargs'] = ast.literal_eval(swh_logging_args_kwargs)

        exception = source.get('swh_logging_args_exc')
        if exception:
            _data['exception'] = exception

        if not _data:
            message = source.get('message')
            if message:
                _data = {
                    'args': {},
                    'kwargs': {},
                    'exception': message
                }

        if _data:
            all_data.append(_data)

    return {
        'all': all_data,
        'last_sort_time': last_sort_time,
        'total_hits': total_hits
    }


def query_log_server(server, indexes, types, size):
    count = 0
    last_sort_time = None
    total_hits = 1

    while count < total_hits:
        response = retrieve_data(server, indexes, types, size,
                                 start=last_sort_time)
        data = format_result(response)
        if not data:
            break

        total_hits = data['total_hits']
        last_sort_time = data['last_sort_time']

        for row in data['all']:
            count += 1
            yield row


@click.command()
@click.option('--server',
              default='http://banco.internal.softwareheritage.org:9200',
              help='Elastic search instance to query against')
@click.option('--indexes',
              default='logstash-2017.05.*,logstash-2017.06.*',
              help='ElasticSearch indexes to lookup (csv if many)')
@click.option('--types', default='journal',
              help='ElasticSearch types to lookup (csv if many)')
@click.option('--size', default=10, type=click.INT, help='Pagination size')
def main(server, indexes, types, size):
    for entry in query_log_server(server, indexes, types, size):
        print(entry)


if __name__ == '__main__':
    main()
