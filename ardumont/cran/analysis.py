# Copyright (C) 2019 The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information


import click
import datetime
import gzip
import re
import logging
import json

from typing import Dict, Tuple, List

from collections import defaultdict
from pprint import pprint

logger = logging.getLogger(__name__)


def validate_date_pattern(date_text, pattern):
    """Validate the date is of a given pattern (strptime like)

    Pattern possible for example: '%Y-%m-%d'
    """
    valid = True
    try:
        datetime.datetime.strptime(date_text, pattern)
    except ValueError:
        valid = False
    return valid


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


def date_field_pattern_repartition(
        data: Dict, field: str = 'Date') -> Tuple[Dict, List]:
    """Analyze date field pattern repartition

    Returns:
        Repartition of date per pattern, List of unknown values

    """
    patterns = [
        '%d %B %Y',   # '21 February 2012',
        '%d %b %Y',
        '%Y-%m-%d',
        '%Y.%m.%d',
        '%d.%m.%Y',
        '%d.%m.%y',
        '%d/%m/%Y',
        '%Y-%d-%m',
        '%Y/%m/%d',
        '%Y-%m-%d %H:%M:%S',
    ]
    return analyze_pattern_repartition(data, patterns,
                                       field, validate_date_pattern)


def validate_author_pattern(field_author, pattern):
    """Validate author field pattern (regexp)

    Pattern possible for example: '%Y-%m-%d'
    """
    return re.match(pattern, field_author)


def author_field_pattern_repartition(
        data: Dict, field: str = 'Maintainer') -> Tuple[Dict, List]:
    """Try and validate the data set for field

    Returns:
        Repartition of author per pattern, List of unknown values

    """
    patterns = [
        # Maintainer fields are ok with the following
        r'[Ø\'"a-zA-Z].*<[a-zA-Z0-9.@].*>.*',
        r'[a-zA-Z].*\n<[a-zA-Z0-9.@].*>',
        r'ORPHANED',
        # Author fields needs more work
        r'[\'ØA-Za-z ].*',
        r'\n',
        r'\t',
    ]
    return analyze_pattern_repartition(data, patterns, field,
                                       validate_author_pattern)


def author_field_repartition(data):
    """Compute field repartition

    """
    summary = defaultdict(int)

    for d in data:
        maintainer = d.get('Maintainer')
        author = d.get('Author')
        if maintainer is not None and author is not None:
            summary['maintainer_and_author'] += 1
        elif maintainer is not None:
            summary['maintainer'] += 1
        elif author is not None:
            summary['author'] += 1
        else:
            summary['no_author_no_maintainer'] += 1

    return dict(summary)


def date_field_repartition(data):
    """Compute field repartition

    """
    summary = defaultdict(int)

    for d in data:
        date = d.get('Date')
        published = d.get('Published')
        if published is not None and date is not None:
            summary['date_and_published'] += 1
        elif date is not None:
            summary['date'] += 1
        elif published is not None:
            summary['published'] += 1
        else:
            summary['no_date_no_published'] += 1

    return dict(summary)


def load_data(filepath):
    """Load data set from filepath (json in gzip file)

    """
    logger.debug('filepath: %s', filepath)
    with gzip.open(filepath) as f:
        data = json.loads(f.read())

    logger.debug('len(data): %s', len(data))
    return data


@click.command()
@click.option('--dataset', help='Json data set as gzip', required=True,
              default='list-all-packages.R.json.gz')
@click.option('--with-pattern-date-repartition', is_flag=True, default=False)
@click.option('--with-author-repartition', is_flag=True, default=False)
@click.option('--with-date-repartition', is_flag=True, default=False)
@click.option('--with-pattern-author-repartition', is_flag=True, default=False)
def main(dataset, with_pattern_date_repartition,
         with_author_repartition, with_date_repartition,
         with_pattern_author_repartition):
    data = load_data(dataset)

    if with_pattern_date_repartition:
        for field in ['Date', 'Published']:
            summary, invalid = date_field_pattern_repartition(
                data, field)
            logger.info("Summary for '%s' field", field)
            pprint(summary)

            logger.info("Unknown date format for '%s' field" % field)
            pprint(invalid)

    if with_pattern_author_repartition:
        for field in ['Maintainer', 'Author']:
            summary, invalid = author_field_pattern_repartition(
                data, field)
            logger.info("Summary for '%s' field", field)
            pprint(summary)

            logger.info("Unknown format for '%s' field" % field)
            pprint(invalid)

    if with_author_repartition:
        summary = author_field_repartition(data)
        pprint(summary)

    if with_date_repartition:
        summary = date_field_repartition(data)
        pprint(summary)


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s %(process)d %(message)s'
    )

    main()
