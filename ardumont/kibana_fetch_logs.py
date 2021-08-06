#!/usr/bin/env python3
# Copyright (C) 2017-2021 the Software Heritage developers
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information

# Configuration file at ~/.config/swh/kibana/query.yml
# configuration sample:
# - https://forge.softwareheritage.org/P221
# - https://forge.softwareheritage.org/P221#7494

# Use:
# ./kibana_fetch_logs.py | tee temporary-error-file


import ast
import click
import logging
import requests

from typing import Any, Dict
from swh.core.config import load_from_envvar


DEFAULT_CONFIG = {
    # ssh tunnel required now: ssh -L 9200:<ip>:9200 <hostname>
    'server': 'http://localhost:9200',
    'indexes': [
        'swh_workers-2017.05.*', 'swh_workers-2017.06.*'
    ],
    'size': 10,
    'from': 0,
    '_source': [
        'message',
        'swh_task_args_0',
    ],
    'sort': [{
        '@timestamp': 'asc'
    }],
    'query': {
        'bool': {
            'must': [
                {
                    'match': {
                        'systemd_unit.keyword': {
                            'query': 'swh-worker@loader_svn.service',
                        }
                    }
                },
                {
                    'term': {
                        'priority': '3'
                    }
                }
            ]
        }
    },
}


logger = logging.getLogger(__name__)


def old_task_information_keys_p(keys):
    """Old format keys for logging task input information

    """
    for k in keys:
        if 'swh_logging_' in k:
            return True
    return False


def old_parse_task_arguments(source, keys):
    """Old format parsing logic

    """
    swh_logging_args_args = source.get('swh_logging_args_args')
    if swh_logging_args_args:
        args = ast.literal_eval(swh_logging_args_args)
    swh_logging_args_kwargs = source.get('swh_logging_args_kwargs')
    if swh_logging_args_kwargs:
        kwargs = ast.literal_eval(swh_logging_args_kwargs)
    exception = source.get('swh_logging_args_exc')
    return args, kwargs, exception


def task_information_keys_p(keys):
    """Are there `swh_task_` keys in the set

    """
    for k in keys:
        logger.debug('#### task_info_keys_p: key %s', k)
        if 'swh_task_' in k:
            return True
    return False


def parse_task_arguments(source, keys):
    """Parse the task arguments as args, kwargs and None (no exception to
       parse).

    """
    task_args = parse_task_args(source, keys)
    task_kwargs = parse_task_kwargs(source, keys)
    exception = None
    return task_args, task_kwargs, exception


def parse_task_args(source, keys=[]):
    """Parse task args

    >>> source = {'swh_task_args_0': 1, 'swh_task_args_1': 2, 'swh_task_kwargs_some': 'one'}
    >>> parse_task_args(source)
    [1, 2]

    """
    if not keys:
        keys = source.keys()
    args = []
    prefix_key = 'swh_task_args_'
    logger.debug('parse-task-args: source: %s', source)
    for k in (k for k in keys if k.startswith(prefix_key)):
        logger.debug('parse-task-args: %s', k)
        index = k.split(prefix_key)[-1]
        args.insert(int(index), source[k])
    return args


def parse_task_kwargs(source, keys=[]):
    """Parse task kwargs

    >>> source = {'swh_task_args_0': 1, 'swh_task_args_1': 2, 'swh_task_kwargs_no': 'one'}  # noqa
    >>> parse_task_kwargs(source)
    {'no': 'one'}

    """
    if not keys:
        keys = source.keys()
    kwargs = {}
    prefix_key = 'swh_task_kwargs_'
    for k in (k for k in keys if k.startswith(prefix_key)):
        logger.debug('parse-task-kwargs: %s', k)
        key_name = k.split(prefix_key)[-1]
        kwargs[key_name] = source[k]

    return kwargs


class KibanaFetchLog:
    """Kibana fetch log class to permit log retrieval.

    """
    CONFIG_BASE_FILENAME = 'kibana/query'

    def __init__(self, config=None):
        self.config: Dict[str, Any] = load_from_envvar(DEFAULT_CONFIG)
        if config:  # permit to amend the configuration file if it exists
            self.config.update(config)

        self.server = self.config['server']
        self.indexes = ','.join(self.config['indexes'])
        self.payload = {
            key: self.config[key]
            for key in ['from', '_source', 'query', 'size', 'sort']
        }
        logger.debug('### Server: %s' % self.server)
        logger.debug('### Indexes: %s' % self.indexes)

    def _retrieve_data(self, server, indexes, start=None):
        """Retrieve information from server looking up through 'indexes'. This
        returns result of length 'size' (configuration) starting from
        the 'start' position.

        """
        payload = self.payload
        if start:
            payload['search_after'] = [start]

        url = '%s/%s/_search' % (server, indexes)

        r = requests.post(url, json=payload)
        logger.debug('Payload: %s' % payload)
        if not r.ok:
            logger.debug('Response: %s' % r.content)
            raise ValueError("Problem when communicating with server: %s" % (
                r.status_code, ))

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
            logger.debug('#### data: %s', data)
            logger.debug('#### source: %s', source)
            _data = {}
            source_keys = source.keys()
            args = []
            kwargs = {}
            exception = None

            if task_information_keys_p(source_keys):
                args, kwargs, exception = parse_task_arguments(
                    source, source_keys)
            elif old_task_information_keys_p(source_keys):  # old logs format
                args, kwargs, exception = old_parse_task_arguments(
                    source, source_keys)
            else:
                logger.warning('Record format unknown: %s, skipping', source)

            _data['args'] = args
            _data['kwargs'] = kwargs
            _data['exception'] = exception if exception else source['message']

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

        while count < total_hits:
            response = self._retrieve_data(
                server, indexes, start=last_sort_time)
            data = self._format_result(response)
            if not data:
                break

            total_hits = data['total_hits']['value']
            last_sort_time = data['last_sort_time']

            for row in data['all']:
                count += 1
                yield row


@click.command()
@click.option('--server', default=None,
              help='Elastic search instance to query against')
@click.option('--indexes', default=None,
              help='ElasticSearch indexes to lookup (csv if many)')
@click.option('--size', default=10, type=click.INT, help='Pagination size')
@click.option('--debug/--nodebug', is_flag=True, default=False)
def main(server, indexes, size, debug):
    logging.basicConfig(level=logging.DEBUG if debug else logging.INFO)

    config = {}
    if server:
        config['server'] = server
    if indexes:
        config['indexes'] = indexes.split(',')
    if size:
        config['size'] = size

    fetcher = KibanaFetchLog(config)
    for entry in fetcher.fetch():
        print(entry)


if __name__ == '__main__':
    main()
