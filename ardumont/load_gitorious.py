#!/usr/bin/env python3

# Copyright (C) 2017  The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information


import click
import os
import sys

from swh.scheduler.utils import get_task


def load_repository_from_mapping(root_repositories_dir, origin_date,
                                 queue_name, dry_run=False):
    """Load a repository from a specific rootdir.
    """
    for line in sys.stdin:
        line = line.strip().split(' ')
        origin_url = line[0]
        relative_repo_on_disk = ' '.join(line[1:])

        # initiate task
        task = get_task('swh.loader.git.tasks.LoadDiskGitRepository')
        # but mutate the queue to use another queue than the default
        task.task_queue = queue_name

        directory_path = os.path.join(
            root_repositories_dir, relative_repo_on_disk)
        date = origin_date

        print('{origin_url: %s, repo: %s, date: %s}' % (
              origin_url, directory_path, date))
        if not dry_run:
            task.delay(origin_url=origin_url,
                       directory=directory_path,
                       date=date)


@click.command()
@click.option('--root-repositories',
              help='Upper root directory for storing repositories.')
@click.option('--origin-date',
              default='Wed, 30 Mar 2016 09:40:04 +0200',
              help='Origin date to use.')
@click.option('--queue-name',
              default='swh_loader_git_express',
              help='''Queue name to use for message,
                      potentially overwriting default one.''')
@click.option('--dry-run/--no-dry-run',
              help='Do nothing but print.')
def run(root_repositories, origin_date, queue_name, dry_run):
    load_repository_from_mapping(
        root_repositories_dir=root_repositories,
        origin_date=origin_date,
        queue_name=queue_name,
        dry_run=dry_run)


if __name__ == '__main__':
    run()
