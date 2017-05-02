#!/usr/bin/env python3

import sys
import os


ROOTDIR = '/srv/storage/space/lists/azure-rehash/'

r = list(map(str, range(0, 10))) + [
    chr(c) for c in range(ord('a'), ord('f')+1)
]

FILES = {}


def all_open():
    for i in r:
        FILES[i] = open(os.path.join(ROOTDIR, i), 'w')


def all_close():
    for i in r:
        FILES[i].close()


def main():
    all_open()
    for h in sys.stdin:
        FILES[h[0]].write(h)
    all_close()


if __name__ == '__main__':
    main()
