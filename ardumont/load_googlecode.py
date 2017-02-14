#!/usr/bin/env python3

# Copyright (C) 2017  The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information


import click
import sys

from swh.scheduler.utils import get_task


def load_repository_from_mapping(origin_date, dry_run=False):
    """Load a repository from a specific rootdir.

    """
    for line in sys.stdin:
        line = line.strip().split(' ')
        origin_url = line[0]
        archive_path = ' '.join(line[1:])

        # initiate task
        task = get_task(
            'swh.loader.git.tasks.UncompressAndLoadDiskGitRepository')

        date = origin_date

        print('{origin_url: %s, archive_path: %s, date: %s}' % (
              origin_url, archive_path, date))
        if not dry_run:
            task.delay(origin_url=origin_url,
                       archive_path=archive_path,
                       date=date)


@click.command()
@click.option('--visit-date',
              default='Tue, 3 May 2016 17:16:32 +0200',
              help='Visit date to use as origin date.')
@click.option('--dry-run/--no-dry-run',
              help='Do nothing but print.')
def run(visit_date, dry_run):
    load_repository_from_mapping(origin_date=visit_date, dry_run=dry_run)


if __name__ == '__main__':
    run()
