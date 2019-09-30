# Copyright (C) 2015-2019  The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information


import click
import requests

from typing import Tuple, Generator, Dict


def list_repos(username: str) -> Generator[Tuple[str, str, Dict], None, None]:
    """Greedily list the repositories per user

    Args:
        username: github's username

    Yields:
        Url
    """
    api_url = 'https://api.github.com/users/%s/repos' % username
    r = requests.get(api_url)
    if r.ok:
        next_link = r.links.get('next')
        for d in r.json():
            yield d

        while next_link:
            r = requests.get(next_link['url'])
            if r.ok:
                next_link = r.links.get('next')
                for d in r.json():
                    yield d
            else:
                next_link = False


@click.command()
@click.option('--user', help='Github username')
def main(user):
    repos = list_repos(user)

    counter = 0
    for repo in repos:
        counter += 1
        print(repo['html_url'])

    print('number of repositories: %s' % counter)


if __name__ == '__main__':
    main()
