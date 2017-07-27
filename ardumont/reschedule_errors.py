#!/usr/bin/env python3

# Copyright (C) 2017  The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information


import ast
import click
import sys


from swh.scheduler.utils import get_task


_MAP_ORIGIN_QUEUE = {
    'gitorious': 'swh.loader.git.tasks.LoadDiskGitRepository',
    'googlecode': 'swh.loader.git.tasks.UncompressAndLoadDiskGitRepository',
}


_BLACK_LISTED_EXCEPTIONS = [
    "NotGitRepository('No git repository was found at /",
    "ValueError('Failed to uncompress archive /srv/stor",
]


def work_on_exception_msg(exception):
    return exception[0:40]


@click.command()
@click.option('--origins', default=['gitorious', 'googlecode'])
@click.option('--dry-run/--no-dry-run', help='Do nothing but print.')
def main(origins, dry_run):
    if dry_run:
        print('*** DRY RUN ***')

    tasks = {k: get_task(v) for k, v in _MAP_ORIGIN_QUEUE.items()}

    black_listed_exceptions = list(map(work_on_exception_msg,
                                       _BLACK_LISTED_EXCEPTIONS))

    for line in sys.stdin:
        line = line.rstrip()
        data = ast.literal_eval(line)
        args = data['args']
        exception = work_on_exception_msg(data['exception'])

        if exception in black_listed_exceptions:
            continue

        ori_type = None
        for ori in origins:
            if ori in args['origin_url']:
                ori_type = ori
                break

        if not ori_type:
            print('origin type \'%s\' unknown' % ori_type)
            continue

        print('%s %s' % (ori_type, data['args']))
        if dry_run:
            continue

        tasks[ori_type].delay(**data['args'])


if __name__ == '__main__':
    main()
