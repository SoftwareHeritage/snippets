#!/usr/bin/env python3
# Copyright (C) 2017-2018 the Software Heritage developers
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information

# Configuration file at ~/.config/swh/kibana/query.yml
# (configuration sample at https://forge.softwareheritage.org/P221)

# Use:
# ./kibana_fetch_logs.py | tee temporary-error-file


import ast
import click
import requests

from swh.core.config import SWHConfig


class KibanaFetchLog(SWHConfig):
    """Kibana fetch log class to permit log retrieval.

    """
    CONFIG_BASE_FILENAME = 'kibana/query'

    DEFAULT_CONFIG = {
        'server': ('str', 'http://banco.internal.softwareheritage.org:9200'),
        'indexes': ('list[str]', ['logstash-2017.05.*', 'logstash-2017.06.*']),
        'types': ('str', 'journal'),
        'size': ('int', 10),
        'from': ('int', 0),
        '_source': ('list[str]', [
            'message',
            'swh_logging_args_args',
            'swh_logging_args_exc',
            'swh_logging_args_kwargs']),
        'sort': ('list', [{
            '@timestamp': 'asc'
        }]),
        'query': ('dict', {
            'bool': {
                'must': [
                    {
                        'match': {
                            'systemd_unit': {
                                'query': 'swh-worker@swh_loader_svn.service',
                                'type': 'phrase'
                            }
                        }
                    },
                    {
                        'term': {
                            'priority': '3'
                        }
                    }
                ],
                'must_not': [
                    {
                        'match': {
                            'message': {
                                'query': "[.*] Property 'svn:externals' detected.",  # noqa
                                'type': 'phrase'
                            }
                        }
                    },
                    {
                        'match': {
                            'message': {
                                'query': '[.*] Uneventful visit. Detail: file',
                                'type': 'phrase'
                            }
                        }
                    },
                    {
                        'match': {
                            'message': {
                                'query': '.*Failed to mount the svn dump.*',
                                'type': 'phrase'
                            }
                        }
                    },
                    {
                        'match': {
                            'message': {
                                'query': '[.*] Loading failure, updating to `partial`',  # noqa
                                'type': 'phrase'}}},
                    {
                        'match': {
                            'message': {
                                'query': '[.*] consumer: Cannot connect to amqp.*',  # noqa
                                'type': 'phrase'}}},
                    {
                        'match': {
                            'message': {
                                'query': '[.*] pidbox command error.*',
                                'type': 'phrase'
                            }
                        }
                    }
                ]
            }
        }),
    }

    ADDITIONAL_CONFIG = {}

    def __init__(self, config=None):
        self.config = self.parse_config_file(
            additional_configs=[self.ADDITIONAL_CONFIG])
        if config:  # permit to amend the configuration file if it exists
            self.config.update(config)

        self.server = self.config['server']
        self.indexes = ','.join(self.config['indexes'])
        self.types = self.config['types']
        self.payload = {
            key: self.config[key]
            for key in ['from', '_source', 'query', 'size', 'sort']
        }

    def _retrieve_data(self, server, indexes, types, start=None):
        """Retrieve information from server looking up through 'indexes' and
        'types'.  This returns result of length 'size' (configuration)
        starting from the 'start' position.

        """
        payload = self.payload
        if start:
            payload['search_after'] = [start]

        url = '%s/%s/%s/_search' % (server, indexes, types)

        r = requests.post(url, json=payload)
        if r.ok:
            return r.json()

    def _format_result(self, json):
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

    def fetch(self):
        """Fetch wanted information (cf. 'query' entry in configuration).

        """
        count = 0
        last_sort_time = None
        total_hits = 1

        server = self.server
        indexes = self.indexes
        types = self.types

        while count < total_hits:
            response = self._retrieve_data(
                server, indexes, types, start=last_sort_time)
            data = self._format_result(response)
            if not data:
                break

            total_hits = data['total_hits']
            last_sort_time = data['last_sort_time']

            for row in data['all']:
                count += 1
                yield row


@click.command()
@click.option('--server', default=None,
              help='Elastic search instance to query against')
@click.option('--indexes', default=None,
              help='ElasticSearch indexes to lookup (csv if many)')
@click.option('--types', default=None,
              help='ElasticSearch types to lookup (csv if many)')
@click.option('--size', default=10, type=click.INT, help='Pagination size')
def main(server, indexes, types, size):
    config = {}
    if server:
        config['server'] = server
    if indexes:
        config['indexes'] = indexes.split(',')
    if types:
        config['types'] = types
    if size:
        config['size'] = size

    fetcher = KibanaFetchLog(config)
    for entry in fetcher.fetch():
        print(entry)


if __name__ == '__main__':
    main()
