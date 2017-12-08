#!/usr/bin/env python3

import click
import os
import sys


def read():
    for line in sys.stdin:
        path = line.rstrip()
        project_name = os.path.basename(os.path.dirname(path))
        if 'eclipselabs' in line:
            source = 'eclipselabs'
            url = 'http://code.google.com/%s/%s/%s/svn/' % (
                source, project_name[0], project_name)
        elif 'apache-extras' in line:
            source = 'apache-extras'
            url = 'http://code.google.com/%s/%s/%s/svn/' % (
                source, project_name[0], project_name)
        elif 'code.google.com' in line:
            source = 'googlecode'
            url = 'http://%s.googlecode.com/svn/' % project_name
        else:
            raise ValueError('Unknown source for path %s' % path)

        yield path, url


@click.command(
    help="Read path from stdin and dumps urls followed by the path...")
def main():
    for path, url in read():
        print('%s %s' % (path, url))


if __name__ == '__main__':
    main()
