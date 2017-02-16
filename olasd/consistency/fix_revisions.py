#!/usr/bin/python3

import logging
import pickle
import os
import sys

from swh.loader.git.reader import GitCommitRemoteReader


def get_revisions_and_origins_from_file(filename):
    revs = {}
    with open(filename, 'r') as f:
        for line in f:
            data = line.strip().split()
            revision, origins = data[0], data[1:]
            revs[revision] = set(origins)

    return revs


def revisions_from_origin(origin_url):
    reader = GitCommitRemoteReader()
    return {
        id.decode(): revision
        for id, revision in reader.load(origin_url).items()
    }


def dump_to_file(filename, data):
    with open('%s.tmp' % filename, 'wb') as f:
        pickle.dump(data, f)
    os.rename('%s.tmp' % filename, filename)


if __name__ == '__main__':
    filename = sys.argv[1]
    snapshot = sys.argv[2]

    if os.path.exists(snapshot):
        with open(snapshot, 'rb') as f:
            revs, parsed_revs, origins = pickle.load(f)
    else:
        revs = get_revisions_and_origins_from_file(filename)

        origins = set()
        for urls in revs.values():
            origins |= {url for url in urls
                        if url.startswith('https://github.com/')}

        parsed_revs = {}
        dump_to_file(snapshot, [revs, parsed_revs, origins])

    ctr = 0
    while origins:
        print("%s origins, %s/%s revs remaining" % (
            len(origins), len(revs) - len(parsed_revs), len(revs)
        ))
        ctr += 1
        origin_url = origins.pop()
        try:
            origin_revs = revisions_from_origin(origin_url)
        except Exception as e:
            logging.exception(e)
            continue
        for id, revision in origin_revs.items():
            if id in revs and id not in parsed_revs:
                parsed_revs[id] = revision
        if ctr >= 10:
            ctr = 0
            dump_to_file(snapshot, [revs, parsed_revs, origins])

    dump_to_file(snapshot, [revs, parsed_revs, origins])
