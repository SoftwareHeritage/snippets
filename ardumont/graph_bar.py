#!/usr/bin/env python3

# dependency: python3-click python3-matplotlib

# file to pass is of the form, for one line: <sha1>\t<length>

import click
import os

from matplotlib import pyplot as plt
from matplotlib import style


def read_length_from_file(path):
    with open(path, 'r') as f:
        for line in f.readlines():
            _, length = line.strip().split('\t')
            yield int(length)


@click.command()
@click.option('--path', required=1,
              help='Path to file holding information to draw')
@click.option('--log/--nolog', default=False,
              help='Graph with logarithmic function')
def main(path, log):
    style.use('ggplot')

    if not os.path.exists(path):
        raise ValueError('Path %s must exist!' % path)

    xs = list(read_length_from_file(path))

    if log:
        plt.hist(xs, bins=100, log=True)
    else:
        plt.hist(xs, bins=100)

    plt.title('Length distribution')
    plt.ylabel('Number of occurrences')
    plt.xlabel('Length')

    plt.show()


if __name__ == '__main__':
    main()
