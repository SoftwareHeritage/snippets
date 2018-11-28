#!/usr/bin/env python3

# Copyright (C) 2018  The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information


import click
import random
from math import floor


def sha1_ranges(number_ranges):
    """Compute `number_ranges` random 'balanced' sha1 ranges.

    Args:
        number_ranges (int): Number of ranges to compute

    Returns:
        List[tuple] of hex [start, end] ranges.

    """
    bits_number = 160
    bound_max = 2**bits_number - 1
    step = floor(bound_max / number_ranges)
    bound_max_minus = bound_max - step

    def to_hex(number):
        return '{:040x}'.format(number)

    ranges = []
    for start, end in zip(
            range(0, bound_max_minus, step), range(step, bound_max, step)):
        hex_start = to_hex(start)
        hex_end = to_hex(end)
        ranges.append((hex_start, hex_end))

    if end < bound_max:
        hex_start = to_hex(end)
        hex_end = to_hex(bound_max)
        ranges.append((hex_start, hex_end))

    random.shuffle(ranges)
    return ranges


@click.command()
@click.option('--task-type', '-t', default='indexer_range_mimetype',
              help='Add task type')
@click.option('--policy', '-p', default='oneshot',
              help='Task policy, either oneshot or recurring')
@click.option('--number-ranges', '-n', default=10,
              help='Number of ranges to compute')
def main(task_type, policy, number_ranges):
    """Compute `number-range` ranges of sha1 (160 bits/20 bytes length)
       for a given `task-type` with a given `policy`.

    Use sample:
    $ python3 -m schedule_csv_range \
              --task-type indexer_range_mimetype \
              --policy recurring \
              --number-ranges 100000 | head -2
    indexer_range_mimetype;recurring;["1acba732df505dad980000000000000000000000", "1acc4ef88b9778f5200000000000000000000000"]  # noqa
    indexer_range_mimetype;recurring;["2e4649906cca2ec6e00000000000000000000000", "2e46f15619114a0e680000000000000000000000"]  # noqa

    Then actually schedule the tasks:
    $ head -1 mimetype.prod.csv | python3 -m swh.scheduler.cli task schedule -c type -c policy -c args --delimiter ';' -

    """
    for r in sha1_ranges(number_ranges):
        print('%s;%s;["%s", "%s"]' % (task_type, policy, r[0], r[1]))


if __name__ == '__main__':
    main()
