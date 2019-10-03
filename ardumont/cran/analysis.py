# Copyright (C) 2019 The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information


import click
import datetime
import gzip
import logging
import json

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


def date_field_pattern_repartition(data, date_field='Date'):
    """Try and validate the data set

    """
    status_date = defaultdict(int)
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
    invalid_dates = []
    for d in data:
        valid = False
        date = d.get(date_field)
        if date is None:
            status_date[None] += 1
            continue
        for pattern in patterns:
            if validate_date_pattern(date, pattern):
                status_date['valid'] += 1
                status_date[pattern] += 1
                valid = True
                continue
        if not valid:
            status_date['invalid'] += 1
            invalid_dates.append(date)

    return status_date, invalid_dates


def author_field_repartition(data):
    """Compute field repartition

    """
    summary = defaultdict(int)

    for d in data:
        maintainer = d.get('Maintainer')
        author = d.get('Author')
        if maintainer is not None and author is not None:
            summary['maintainer_and_author'] += 1
        elif maintainer:
            summary['maintainer'] += 1
        elif author:
            summary['author'] += 1
        else:
            summary['no_author_no_maintainer'] += 1

    return summary


def date_field_repartition(data):
    """Compute field repartition

    """
    summary = defaultdict(int)

    for d in data:
        date = d.get('Date')
        published = d.get('Published')
        if published is not None and date is not None:
            summary['date_and_published'] += 1
        elif date:
            summary['date'] += 1
        elif published:
            summary['published'] += 1
        else:
            summary['no_date_no_published'] += 1

    return summary


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
def main(dataset, with_pattern_date_repartition,
         with_author_repartition, with_date_repartition):
    data = load_data(dataset)

    if with_pattern_date_repartition:
        for field_date in ['Date', 'Published']:
            summary, invalid_dates = date_field_pattern_repartition(
                data, field_date)
            logger.info("Summary for '%s' field", field_date)
            pprint(summary)

            logger.info("Unknown date format for '%s' field" % field_date)
            pprint(invalid_dates)

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
