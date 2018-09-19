#!/usr/bin/env python3

"""compute Rabin fingerprints of Software Heritage content objects

Read a list of Software Heritage content object IDs on standard input, fetch
each of them from a (local) object storage and apply Rabin fingerprinting to
its content. Store in a (postgres) DB the mapping between content objects and
(Rabin-delimited) chunks.

"""

import sys
from swh.model.hashutil import hash_to_bytes

from deduper.deduper import Deduper

OBJS_ROOT = '/home/seirl/content-samples'
OBJS_SLICING = '0:2/2:4'
DB_SERVICE = 'swh-dedup'  # postgres service name


def main():
    deduper = Deduper(DB_SERVICE, OBJS_ROOT, OBJS_SLICING)
    for line in sys.stdin:  # schedule tasks
        content_id = line.rstrip()
        deduper.dedup(hash_to_bytes(content_id))


if __name__ == '__main__':
    main()
