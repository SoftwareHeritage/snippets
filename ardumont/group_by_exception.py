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
import sys

from collections import defaultdict, OrderedDict


def work_on_exception_msg(exception):
    return exception[0:50]


def group_by(origin_types):
    group = {ori_type: defaultdict(list) for ori_type in origin_types}

    for line in sys.stdin:
        origin_type = None
        line = line.strip()
        data = ast.literal_eval(line)
        for ori_type in origin_types:
            if ori_type in data['args']['origin_url']:
                origin_type = ori_type
                break

        if not origin_type:
            continue

        reworked_exception_msg = work_on_exception_msg(data['exception'])
        group[origin_type][reworked_exception_msg].append(data['args'])

    return group


@click.command()
@click.option('--origin-types', default=['gitorious', 'googlecode'],
              help='Default types of origin to lookup')
def main(origin_types):
    group = group_by(origin_types)

    result = {}
    for ori_type in origin_types:
        _map = {}
        total = 0
        for k, v in group[ori_type].items():
            l = len(v)
            _map[k] = l
            total += l

        out = sorted(_map.items(), key=operator.itemgetter(1),
                     reverse=True)

        result[ori_type] = {
            'total': total,
            'errors': OrderedDict(out),
        }

    print(json.dumps(result))


if __name__ == '__main__':
    main()
