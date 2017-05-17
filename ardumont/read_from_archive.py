# Copyright (C) 2017  The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information


import click
import gzip


@click.command(help="Read an archive's content from a given position")
@click.option('--archive-path', required=1,
              help='Path to archive')
@click.option('--start-position', required=1, type=click.INT, default=0,
              help='Position to start from')
@click.option('--read-lines', required=1, type=click.INT, default=10,
              help='Number of lines to read (default to 10)')
def main(archive_path, start_position, read_lines):
    if start_position != 0:
        start_position = (start_position - 1) * 41

    with gzip.open(archive_path, 'rb') as f:
        f.seek(start_position)

        count = 1
        for line in f:
            print(line.decode('utf-8').rstrip())
            count += 1
            if count > read_lines:
                break


if __name__ == '__main__':
    main()
