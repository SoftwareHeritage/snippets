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
import re
import sys

from collections import defaultdict, OrderedDict


LOADER_TYPES = ['git', 'svn', 'hg']


def work_on_exception_msg(exception):
    exception_msg = None
    if exception.startswith('['):
        exception_msg = re.sub('\[.*\]', '', exception).lstrip()
    else:
        exception_msg = exception
    return exception_msg[0:50]


def group_by(origin_types, loader_type):
    group = {ori_type: defaultdict(list) for ori_type in origin_types}

    if loader_type == 'svn':
        # args = ('path-to-archive', 'some-origin-url')
        origin_key_to_lookup = 1
    elif loader_type in ['git', 'hg']:
        origin_key_to_lookup = 'origin_url'

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

        reworked_exception_msg = work_on_exception_msg(data['exception'])
        group[origin_type][reworked_exception_msg].append(data['args'])

    return group


@click.command()
@click.option('--origin-types', default=['gitorious', 'googlecode'],
              help='Default types of origin to lookup')
@click.option('--loader-type', default='svn',
              help="Type of loader (%s)" % ', '.join(LOADER_TYPES))
def main(origin_types, loader_type):
    if loader_type not in LOADER_TYPES:
        raise ValueError('Bad input, loader type is one of %s' % LOADER_TYPES)

    origin_types = origin_types + ['unknown']
    group = group_by(origin_types, loader_type)

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

        result[ori_type] = {
            'total': total,
            'errors': OrderedDict(out),
        }

    print(json.dumps(result))


if __name__ == '__main__':
    main()
