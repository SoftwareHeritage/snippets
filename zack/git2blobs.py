#!/usr/bin/env python3

"""crawl a local Git repository and write all the blobs it contains to a
Software Heritage like on-disk object storage

"""

import click
import dulwich
import gzip
import shutil

from dulwich.repo import Repo
from pathlib import Path
from tqdm import tqdm


class PathlibPath(click.Path):
    """A Click path argument that returns a pathlib Path, not a string"""
    def convert(self, value, param, ctx):
        return Path(super().convert(value, param, ctx))


def store_blob(obj, objstorage_dir):
    sha1 = obj.id.decode('ascii')
    obj_path = objstorage_dir / sha1[0:2] / sha1[2:4] / sha1
    if obj_path.exists():
        return

    obj_path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(obj_path, 'wb') as obj_f:
        for data in obj.chunked:
            obj_f.write(data)


@click.command()
@click.option('--repository', '-r', 'repo_dir', metavar='DIR',
              type=PathlibPath(exists=True, readable=True,
                               file_okay=False, dir_okay=True),
              required=True,
              help='on-disk git respository input to crawl')
@click.option('--objstorage', '-o', 'objstorage_dir', metavar='DIR',
              type=PathlibPath(writable=True, file_okay=False, dir_okay=True),
              required=True,
              help='root directory of the output object storage')
@click.option('--tar/--no-tar', '-t', 'use_tar',
              default=False,
              help='tar object storage directory (and remove it!) after '
              "extraction (default: don't tar)")
def main(repo_dir, objstorage_dir, use_tar):
    repo_dir = Path(repo_dir)
    objstorage_dir = Path(objstorage_dir)

    repo = Repo(repo_dir)
    objs = repo.object_store

    objcount = len(list(objs))
    for sha1 in tqdm(objs, desc='writing blobs', unit='obj', total=objcount):
        obj = objs[sha1]
        if isinstance(obj, dulwich.objects.Blob):
            store_blob(obj, objstorage_dir)

    if use_tar:
        shutil.make_archive(objstorage_dir, 'tar', objstorage_dir)
        shutil.rmtree(objstorage_dir)


if __name__ == '__main__':
    main()
