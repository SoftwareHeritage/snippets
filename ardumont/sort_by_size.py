#!/usr/bin/env python3

import click
import os
import sys


def read():
    for line in sys.stdin:
        line = line.rstrip()
        values = line.split(' ')
        path = values[0]
        url = values[1]
        yield path, url


@click.command(
    help="Read path from stdin and dumps urls followed by the path...")
def main():
    for path, url in read():
        print('%s %s %s' % (os.stat(path).st_size, path, url))


if __name__ == '__main__':
    main()
