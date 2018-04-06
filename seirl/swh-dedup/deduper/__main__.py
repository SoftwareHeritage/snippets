import sys
from swh.model.hashutil import hash_to_bytes

from deduper.deduper import Deduper

OBJS_ROOT = '/home/seirl/swh-storage'
OBJS_SLICING = '0:2/2:4/4:6'
DB_SERVICE = 'swh-dedup'  # postgres service name


def main():
    deduper = Deduper(DB_SERVICE, OBJS_ROOT, OBJS_SLICING)
    for line in sys.stdin:  # schedule tasks
        content_id = line.rstrip()
        deduper.dedup(hash_to_bytes(content_id))


if __name__ == '__main__':
    main()
