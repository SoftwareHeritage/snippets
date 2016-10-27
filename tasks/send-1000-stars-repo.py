#!/usr/bin/env python3

import click
import logging
import json
import time

import requests
from urllib.parse import quote

from swh.scheduler.celery_backend.config import app
from swh.loader.git import tasks  # noqa


def parse_links(links):
    """Parse links
    Args:
        links (dict): with keys next and last

    """
    next_link = links['next']['url']
    last_link = links['last']['url']

    return next_link, last_link


# max sleeping time in seconds
MAX_SLEEP = 3600


def list_repositories(start_page=None, last_page=None):
    """List desired gh repositories.

    """
    next_page = 'https://api.github.com/search/repositories?q=%s&per_page=100' % quote(
        'stars:>=1000')

    if start_page:
        next_page = '%s&page=%s' % (next_page, start_page)
    if last_page:
        last_page = '%s&page=%s' % (next_page, last_page)

    while True:
        logging.info('Querying: %s' % next_page)
        r = requests.get(next_page)
        rate_limit = r.headers['X-RateLimit-Remaining']

        logging.debug('Remaining %s' % rate_limit)

        if r.ok:
            data = r.json()
            next_page = r.links.get('next')
            if next_page:
                next_page = next_page['url']

            last_page = r.links.get('last')
            if last_page:
                last_page = last_page['url']

            print('Repos: %s ' % len(data['items']))
            for repo in data['items']:
                yield repo

        # detect throttling, pause computations
        if r.status_code == 403 or rate_limit == 0:
            delay = int(r.headers['X-RateLimit-Reset']) - time.time()
            delay = min(delay, MAX_SLEEP)
            logging.warn('rate limited upon, sleep for %d seconds' %
                         int(delay))
            time.sleep(delay)

        if not next_page or not last_page or next_page == last_page:
            break


@click.command()
@click.option('--queue', default="swh.loader.git.tasks.ReaderGitRepository",
              help="Destination queue to send results")
@click.option('--start-page', default=None, help='Starting page to read from')
@click.option('--last-page', default=None, help='Ending page')
@click.option('--dump-repositories', default='/tmp/repositories',
              help='Default path to keep the list of repositories')
def main(queue, start_page, last_page, dump_repositories):
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s %(process)d %(message)s'
    )

    if start_page:
        start_page = int(start_page)

    if last_page:
        last_page = int(last_page)

    task_destination = app.tasks[queue]

    if dump_repositories:
        f = open(dump_repositories, 'w+')

    for repo in list_repositories(start_page):
        url = repo['html_url']
        task_destination.delay(url)
        f.write('%s %s\n' % (url, repo['stargazers_count']))
        logging.info(url)

    if dump_repositories:
        f.close()

if __name__ == '__main__':
    main()
