#!/usr/bin/env python3

# Copyright (C) 2018  The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information


import click
from math import floor


@click.command()
@click.option('--task-type', '-t', default='indexer_range_mimetype',
              help='Add task type')
@click.option('--policy', '-p', default='oneshot',
              help='Task policy, either oneshot or recurring')
@click.option('--number', '-n', default=10,
              help='Number of ranges to compute')
def main(task_type, policy, number):
    """Compute ranges of sha1 (160 bits/20 bytes length)

    """
    # bits_number = 10
    bits_number = 160
    bound_max = 2**bits_number - 1
    step = floor(bound_max / number)
    bound_max_minus = bound_max - step

    def to_hex(number):
        return '{:040x}'.format(number)

    for start, end in zip(
            range(0, bound_max_minus, step), range(step, bound_max, step)):
        hex_start = to_hex(start)
        hex_end = to_hex(end)
        print('%s;%s;["%s", "%s"]' % (task_type, policy, hex_start, hex_end))

    if end < bound_max:
        hex_start = to_hex(end)
        hex_end = to_hex(bound_max)
        print('%s;%s;["%s", "%s"]' % (task_type, policy, hex_start, hex_end))


if __name__ == '__main__':
    main()
