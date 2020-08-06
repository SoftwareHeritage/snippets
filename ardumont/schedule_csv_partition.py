#!/usr/bin/env python3

# Copyright (C) 2018-2020  The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information


import click
import random


@click.command()
@click.option('--task-type', '-t', default='index-mimetype-partition',
              help='Add task type')
@click.option('--policy', '-p', default='oneshot',
              help='Task policy, either oneshot or recurring')
@click.option('--number-partitions', '-n', default=100000,
              help='Number of ranges to compute')
def main(task_type, policy, number_partitions):
    """Compute `number-partitions` for a given `task-type` with a given `policy`.

    Use sample:
    $ python3 -m schedule_csv_partition \
              --task-type index-mimetype-partition \
              --policy recurring \
              --number-ranges 100000 | head -2
    index-mimetype-partition;oneshot;[30936, 100000]
    index-mimetype-partition;oneshot;[72794, 100000]

    Schedule the tasks (providing file.csv contains the result of the previous
    command):

    $ head -1 file.csv | python3 -m swh.scheduler.cli task schedule \
        -c type -c policy -c args --delimiter ';' -

    """
    partition_ids = [partition_id for partition_id in range(number_partitions)]
    random.shuffle(partition_ids)

    assert len(partition_ids) == number_partitions

    for partition_id in partition_ids:
        print(
            f"{task_type};{policy};[{partition_id}, {number_partitions}]"
        )


if __name__ == '__main__':
    main()
