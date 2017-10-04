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
    'git-gitorious': 'swh.loader.git.tasks.LoadDiskGitRepository',
    'git-googlecode': 'swh.loader.git.tasks.UncompressAndLoadDiskGitRepository',
    'svn-googlecode': 'swh.loader.svn.tasks.MountAndLoadSvnRepositoryTsk'
}


_BLACK_LISTED_EXCEPTIONS = [
    "NotGitRepository('No git repository was found at /",
    "ValueError('Failed to uncompress archive /srv/stor",
]

"""Loader types"""
LOADER_TYPES = ['git', 'svn']


def work_on_exception_msg(exception):
    return exception[0:40]


@click.command()
@click.option('--origins',
              help='Origin concerned by scheduling back',
              default=['gitorious', 'googlecode'])
@click.option('--loader-type', )
@click.option('--dry-run/--no-dry-run', help='Do nothing but print.')
def main(origins, loader_type, dry_run):
    if dry_run:
        print('*** DRY RUN ***')

    tasks = {k: get_task(v) for k, v in _MAP_ORIGIN_QUEUE.items()}

    black_listed_exceptions = list(map(work_on_exception_msg,
                                       _BLACK_LISTED_EXCEPTIONS))

    if loader_type == 'svn':
        # args = ('path-to-archive', 'some-origin-url')
        origin_key_to_lookup = 1
    elif loader_type == 'git':
        # args = {'origin_url: 'some-origin-url}
        origin_key_to_lookup = 'origin_url'

    for line in sys.stdin:
        line = line.rstrip()
        data = ast.literal_eval(line)
        args = data['args']
        exception = work_on_exception_msg(data['exception'])

        if exception in black_listed_exceptions:
            continue

        ori_type = None
        for ori in origins:
            url = args[origin_key_to_lookup]
            if ori in url:
                ori_type = '-'.join([loader_type, ori])
                break

        if not ori_type:
            print('origin type \'%s\' unknown' % ori_type)
            continue

        print('%s %s' % (ori_type, data['args']))
        if dry_run:
            continue

        if loader_type == 'svn':
            tasks[ori_type].delay(*data['args'])
        else:
            tasks[ori_type].delay(**data['args'])


if __name__ == '__main__':
    main()
