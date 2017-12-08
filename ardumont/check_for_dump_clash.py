#!/usr/bin/env python3

import click
import os
import sys

from collections import defaultdict


def read():
    m = defaultdict(list)
    for line in sys.stdin:
        path = line.rstrip()
        project_name = os.path.basename(os.path.dirname(path))
        m[project_name].append(path)

    for project_name, paths in m.items():
        if len(paths) > 1:
            yield project_name, paths


@click.command(
    help="""Dump code.google.com path for which a name clash exists in dumps
            coming from apache-extras and eclipselabs...""")
def main():
    for project_name, paths in read():
        for path in paths:
            if 'apache-extras' not in path and 'eclipselabs' not in path:
                print(path)


if __name__ == '__main__':
    main()
