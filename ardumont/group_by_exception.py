#!/usr/bin/env python3

# Copyright (C) 2017 the Software Heritage developers
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information

# Use:
# ./kibana_fetch_logs.py | tee temporary-error-file | \
#    ./group_by_exception.py > temporary-error-file-groupby-exception

import ast
import click
import sys

from collections import defaultdict


def work_on_exception_msg(exception):
    return exception[0:30]


@click.command()
@click.option('--file', help='File to read data from')
def main(file):
    group = defaultdict(list)

    for line in sys.stdin:
        line = line.strip()
        data = ast.literal_eval(line)
        reworked_exception_msg = work_on_exception_msg(data['exception'])
        group[reworked_exception_msg].append(data['args'])

    result = {}
    for k, v in group.items():
        result[k] = len(v)

    print(result)


if __name__ == '__main__':
    main()
