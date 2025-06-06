#!/usr/bin/env python3

# Copyright (C) 2020 the Software Heritage developers
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information

# Use sample
# python3 -m group_by_extension --file-with-failures all-failures.json  | jq .
# {
#   ".tar.gz": 308,
#   ".tar.xz": 152,
#   "download": 102,
#   ".tar.bz2": 79,
#   ".tbz": 79,
#   ".tgz": 40,
#   ".zip": 23,
#   ".tar.lz": 6,
#   ".lisp": 1,
#   ".1.0": 1,
#   "": 1,
#   ".el?id=dcc9ba03252ee5d39e03bba31b420e0708c3ba0c": 1,
#   ".11": 1,
#   ".tar.z": 1,
#   ".1.5": 1,
#   ".4.2": 1,
#   ".sf3": 1,
#   ".7z": 1,
#   "21": 1,
#   ".install.gz": 1,
#   ".gz": 1,
#   ".tar.lzma": 1,
#   ".14.6": 1,
#   ".tar.gz?uuid=tklib-0-6": 1,
#   ".tar.Z": 1,
#   ".1": 1,
#   ".py": 1,
#   "use_minizip": 1,
#   "?p=mmh;a=snapshot;h=431604647f89d5aac7b199a7883e98e56e4ccf9e;sf=tgz": 1,
#   ".8.3;sf=tgz": 1,
#   ".git;a=snapshot;h=V7_3_0p3;sf=tgz": 1,
#   ".0-tar.gz": 1,
#   ".tar": 1
# }


import json
import operator
import os

from collections import defaultdict, OrderedDict
from typing import Dict, List

import click

known_single_extension = [
    ".zip", ".tbz", ".tbz2", ".7z", ".tar", ".lisp", ".el", ".py", ".tgz",
    ".sf3"
]


@click.command()
@click.option('--file-with-failures',
              help='JSON File with list of origins with failures')
def main(file_with_failures):
    with open(file_with_failures, 'r') as f:
        data = json.loads(f.read())

    url_per_extension: Dict[str, List[str]] = defaultdict(list)
    for url in data:
        prefix, ext = os.path.splitext(url)
        if not ext:
            # fallback on using the basename of the url
            url_per_extension[os.path.basename(url)].append(url)
            continue

        if ext in known_single_extension:  # known unique extension
            url_per_extension[ext].append(url)
            continue

        prefix, ext2 = os.path.splitext(prefix)
        if not ext2:  # unique extension
            url_per_extension[ext].append(url)
            continue

        # etension is double e.g. .tar.gz, etc...
        url_per_extension[f"{ext2}{ext}"].append(url)

    # Simplify the following into less steps
    summary: Dict[str, int] = {}
    for ext, urls in url_per_extension.items():
        summary[ext] = len(urls)

    out = sorted(summary.items(), key=operator.itemgetter(1),
                 reverse=True)
    summary = OrderedDict(out)

    print(json.dumps(summary))


if __name__ == '__main__':
    main()
