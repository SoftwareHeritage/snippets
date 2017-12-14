#!/usr/bin/env python3

import click
import os
import sys

from collections import defaultdict


def clash_from_stdin():
    m = defaultdict(list)
    for line in sys.stdin:
        path = line.rstrip()
        project_name = os.path.basename(os.path.dirname(path))
        m[project_name].append(path)

    return m


def filter_clashed_paths():
    """Yields the list of path with clash in names.

    """
    clashes = clash_from_stdin()
    for project_name, paths in clashes.items():
        if len(paths) > 1:
            yield project_name, paths


def filter_unclashed_paths():
    """Yields the paths with no clash in names.

    """
    clashes = clash_from_stdin()
    for project_name, paths in clashes.items():
        if len(paths) == 1:
            yield project_name, paths


@click.command(
    help="""Dump code.google.com paths for which a name clash exists (or no
            clash) in dumps coming from apache-extras and
            eclipselabs...""")
@click.option('--filter-clash/--no-filter-clash', is_flag=True, default=True)
def main(filter_clash):
    fn = filter_clashed_paths if filter_clash else filter_unclashed_paths
    for project_name, paths in fn():
        for path in paths:
            print(project_name, path)


if __name__ == '__main__':
    main()
