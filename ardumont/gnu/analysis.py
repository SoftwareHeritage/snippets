# Copyright (C) 2019 The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information


import click
import datetime
import gzip
import json
import logging
import os
import re
import requests

from typing import Dict, Tuple, List
from pathlib import Path

from collections import defaultdict
from pprint import pprint

from swh.lister.gnu.tree import GNUTree


logger = logging.getLogger(__name__)


def validate_pattern(value, pattern):
    """Validate value with pattern

    """
    return re.match(pattern, value)


def analyze_pattern_repartition(data, patterns, field, validate_pattern_fn):
    repartition = defaultdict(int)
    invalid = []
    for d in data:
        valid = False
        value = d.get(field)
        if value is None:
            repartition[None] += 1
            continue
        for pattern in patterns:
            if validate_pattern_fn(value, pattern):
                repartition['valid'] += 1
                repartition[pattern] += 1
                valid = True
                continue
        if not valid:
            repartition['invalid'] += 1
            invalid.append(value)

    return dict(repartition), invalid


def version_pattern_repartition(
        data: Dict, field: str = 'filename') -> Tuple[Dict, List]:
    """Analyze date field pattern repartition

    Returns:
        Repartition of date per pattern, List of unknown values

    """
    patterns = [
        # '[a-zA-Z0-9].*\.(zip|tar\.gz)',
        '[a-zA-Z].*\.[a-zA-Z].*\.[a-zA-Z].*',
        '[a-zA-Z].*-[0-9.-_].*.(tar\.*|zip)',
    ]
    return analyze_pattern_repartition(data, patterns,
                                       field, validate_pattern)

def filter_noise(data: Dict) -> Dict:
    m = []
    for project, artifacts in data.items():
        for artifact in artifacts:
            filename = os.path.basename(artifact['archive'])
            m.append({'filename': filename})
    return m


@click.command()
@click.option('--dataset', help='Json data set as gzip', required=True,
              default='tree.json.gz')
def main(dataset):
    tree_json = GNUTree(dataset)
    raw_data = tree_json._load_raw_data()
    pprint(raw_data)

    # data = filter_noise(tree_json.artifacts)
    # summary, invalid = version_pattern_repartition(data)

    # print("Regexp filename repartition")
    # pprint(summary)

    # print("Unknown format")
    # if len(invalid) < 100:
    #     pprint(invalid)
    # else:
    #     print('Too many invalid (%s), show first 100' % len(invalid))
    #     pprint(invalid[0:100])


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s %(process)d %(message)s'
    )

    main()
