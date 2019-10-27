#!/usr/bin/env python3

"""Crawl a local Git repository and write a map <SHA1, FILENAME> of all file
*names* (not paths) given to all blobs found in the repository.

As file names might be in general non readable, the map is actually emitted
twice, once with hex-encoded file names (for those who really want all file
names), another with utf8-encoded file names (skipping all non-utf8-encodable
names).  If you want only one of the two, write the other to /dev/null.

"""

import dulwich
import gzip
import sys

from dulwich.repo import Repo
from pathlib import Path
from tqdm import tqdm
from typing import Set, Tuple


GIT_BLOB_MODES = {0o100644, 0o100755}


def collect_blob_entries(object_store) -> Set[Tuple[bytes, bytes]]:
    """collect all <blob_sha1, filename> entries in memory, deduplicating"""
    blob_entries: Set[Tuple[bytes, bytes]] = set()  # <sha1, filename>
    objcount = len(list(object_store))

    for sha1 in tqdm(object_store, desc='collecting filenames',
                     unit='obj', total=objcount):
        obj = object_store[sha1]
        if not isinstance(obj, dulwich.objects.Tree):
            continue
        for entry in obj.items():
            if entry.mode in GIT_BLOB_MODES:
                blob_entries.add((entry.sha, entry.path))

    return blob_entries


def emit_blob_entries(blob_entries, hex_names: Path, utf8_names: Path) -> None:
    """emit sorted <sha1, filename> entries to the given gzipped files

    note that the gzip files are appended to, so you can incrementally add
    other pairs to them (the *resulting* maps will not be sorted in that case
    though)

    """
    with gzip.open(hex_names, 'at', encoding='ascii') as hex_f, \
         gzip.open(utf8_names, 'at', encoding='utf8') as utf8_f:  # NoQA
        for (sha, filename) in tqdm(sorted(blob_entries),
                                    desc='writing filenames',
                                    unit='name', total=len(blob_entries)):
            target = sha.decode('ascii')
            print(target, filename.hex(), sep='\t', file=hex_f)
            try:
                print(target, filename.decode('utf8'), sep='\t', file=utf8_f)
            except UnicodeDecodeError:
                pass


def main(repo_dir: Path, hex_names: Path, utf8_names: Path) -> None:
    repo = Repo(repo_dir)
    blob_entries = collect_blob_entries(repo.object_store)
    emit_blob_entries(blob_entries, hex_names, utf8_names)


if __name__ == '__main__':
    try:
        repo_dir = Path(sys.argv[1])
        hex_names = Path(sys.argv[2])
        utf8_names = Path(sys.argv[3])
        main(repo_dir, hex_names, utf8_names)
    except IndexError:
        print('Usage: git2objstorage REPO_DIR GZIP_HEX_OUT GZIP_UTF8_OUT')
        sys.exit(1)
