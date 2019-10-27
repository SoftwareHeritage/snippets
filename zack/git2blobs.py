#!/usr/bin/env python3

import dulwich
import gzip
import sys

from dulwich.repo import Repo
from pathlib import Path
from tqdm import tqdm


def store_blob(obj, objstorage_dir):
    sha1 = obj.id.decode('ascii')
    obj_path = objstorage_dir / sha1[0:2] / sha1[2:4] / sha1
    obj_path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(obj_path, 'wb') as obj_f:
        for data in obj.chunked:
            obj_f.write(data)


def main(repo_dir, objstorage_dir):
    repo = Repo(repo_dir)
    objs = repo.object_store

    objcount = len(list(objs))
    for sha1 in tqdm(objs, desc='writing blobs', unit='obj', total=objcount):
        obj = objs[sha1]
        if isinstance(obj, dulwich.objects.Blob):
            store_blob(obj, objstorage_dir)


if __name__ == '__main__':
    try:
        main(sys.argv[1], Path(sys.argv[2]))
    except IndexError:
        print('Usage: git2objstorage REPO_DIR OBJSTORAGE_DIR')
        sys.exit(1)
