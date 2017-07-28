#!/usr/bin/env python3

# Use sample:
# cat loader-git-disk-errors-july-27-28-2017 | grep googlecode | grep NotGitRepository | ./list-origin-per-error.py

import ast
import click
import sys


@click.command()
def main():
    for line in sys.stdin:
        line = line.rstrip()
        data = ast.literal_eval(line)
        args = data['args']
        if 'gitorious' in args['origin_url']:
            key = 'directory'
        elif 'googlecode' in args['origin_url']:
            key = 'archive_path'
        else:
            continue
        print('%s %s' % (args['origin_url'], args[key]))


if __name__ == '__main__':
    main()
