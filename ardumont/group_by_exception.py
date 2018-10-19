#!/usr/bin/env python3

# Copyright (C) 2017 the Software Heritage developers
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information

# Use:
# ./kibana_fetch_logs.py | tee temporary-error-file | \
#    ./group_by_exception.py | jq > temporary-error-file-groupby-exception

import ast
import click
import json
import operator
import os
import re
import sys
import yaml

from collections import defaultdict, OrderedDict


LOADER_TYPES = ['git', 'svn', 'hg', 'pypi']


def work_on_exception_msg(errors, exception):
    """Try and detect the kind of exception

    """
    # first try to detect according to existing and known errors
    for error in errors:
        if error in exception:
            return error

    # if no standard error is found, group by end of exception message
    exception_msg = None
    if exception.startswith('['):
        exception_msg = re.sub('\[.*\]', '', exception).lstrip()
    else:
        exception_msg = exception
    return exception_msg[-50:]


ORIGIN_KEY_TO_LOOKUP = {
    'svn': 1,
    'pypi': 1,
    'git': 0,
    'hg': 'origin_url',
}


def group_by_origin_types(origin_types, loader_type, errors):
    """Group origins per origin type, error type.

    """
    group = {ori_type: defaultdict(list) for ori_type in origin_types}
    # solve where to look for origin-url information
    origin_key_to_lookup = ORIGIN_KEY_TO_LOOKUP[loader_type]

    seen = set()
    for line in sys.stdin:
        origin_type = None
        origin_url = None
        line = line.strip()
        data = ast.literal_eval(line)
        args = data['args']
        if not args:  # possibly the input is different for that loader
            args = data['kwargs']

        for ori_type in origin_types:
            try:
                if args and ori_type in args[origin_key_to_lookup]:
                    origin_type = ori_type
                    origin_url = args[origin_key_to_lookup]
                    break
            except IndexError:  # when something is wrong, just be the unknown
                                # origin_type
                break

        # corner case when we don't have the input parameters (both
        # args and kwargs to None)
        if not origin_type:
            origin_type = 'unknown'

        if origin_url:
            if origin_url in seen:
                continue

            seen.add(origin_url)

        reworked_exception_msg = work_on_exception_msg(
            errors, data['exception'])
        group[origin_type][reworked_exception_msg].append(data['args'])

    return group


def group_by(loader_type, errors):
    """Group origins per error type.

    """
    group = defaultdict(list)
    seen = set()
    for line in sys.stdin:
        origin_url = None
        line = line.strip()
        data = ast.literal_eval(line)
        args = data['args']
        if not args:  # possibly the input is different for that loader
            args = data['kwargs']

        if origin_url:
            if origin_url in seen:
                continue

            seen.add(origin_url)

        reworked_exception_msg = work_on_exception_msg(
            errors, data['exception'])
        group[reworked_exception_msg].append(data['args'])

    return group


@click.command()
@click.option('--origin-types',
              default=['gitorious', 'googlecode', 'pypi', 'git'],
              multiple=True, help='Default types of origin to lookup')
@click.option('--loader-type', default='svn',
              help="Type of loader (%s)" % ', '.join(LOADER_TYPES))
@click.option('--config-file',
              default=os.path.expanduser('~/.config/swh/kibana/group-by.yml'),
              help='Default configuration file')
@click.option('--aggregate/--no-aggregate', is_flag=True, default=True,
              help='Aggregate by origin types (default)')
def main(origin_types, loader_type, config_file, aggregate):
    if loader_type not in LOADER_TYPES:
        raise ValueError('Bad input, loader type is one of %s' % LOADER_TYPES)

    if not os.path.exists(config_file):
        raise ValueError('Bad setup, you need to provide a configuration file')

    with open(config_file, 'r') as f:
        data = yaml.load(f.read())

    errors = data.get('errors')
    if not errors:
        err = 'Bad config, please provide the errors per loader-type'
        raise ValueError(err)

    if loader_type not in errors:
        err = 'Bad config, please provide the errors for loader-type %s' % (
            loader_type)
        raise ValueError(err)

    if aggregate:  # by origin types
        origin_types = list(origin_types)
        origin_types.append('unknown')
        group = group_by_origin_types(
            origin_types, loader_type, errors[loader_type])
        result = {}
        for ori_type in origin_types:
            _map = {}
            total = 0
            for k, v in group[ori_type].items():
                _len = len(v)
                _map[k] = _len
                total += _len

            out = sorted(_map.items(), key=operator.itemgetter(1),
                         reverse=True)

            if total != 0:
                result[ori_type] = {
                    'total': total,
                    'errors': OrderedDict(out)
                }
    else:
        group = group_by(loader_type, errors[loader_type])
        _map = {}
        total = 0
        for error, origins in group.items():
            _len = len(origins)
            _map[error] = _len
            total += _len

        out = sorted(_map.items(), key=operator.itemgetter(1),
                     reverse=True)
        result = {
            'total': total,
            'errors': OrderedDict(out),
        }

    print(json.dumps(result))


if __name__ == '__main__':
    main()
