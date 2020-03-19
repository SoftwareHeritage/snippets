#!/usr/bin/env python3

import logging

import click
import requests

from typing import Any, Dict


logger = logging.getLogger(__name__)


SENTRY_URL = 'https://sentry.softwareheritage.org'


def url_project(base_url: str) -> str:
    return f'{base_url}/api/0/projects/'


def url_api_token(base_url: str) -> str:
    return f'{base_url}/settings/account/api/auth-tokens/'


@click.command()
@click.option('-a', '--api-url', default=SENTRY_URL, help='sentry api to use')
@click.option('-t', '--token', help='Api authentication token')
def main(api_url: str, token: str) -> Dict[str, Any]:
    if not token:
        token_url = url_api_token(api_url)
        raise ValueError(
            f'Missing api token, connect and generate one in {token_url}'
        )

    url = url_project(api_url)
    logger.debug('api_url: %(url)s, token: %(token)s', {
        'url': url,
        'token': token,
    })
    resp = requests.get(url, headers={
        'Authorization': f'Bearer {token}',
        'content-type': 'application/json'
    })

    if resp.ok:
        logger.debug('resp: %(resp)s', {'resp': resp})
        logger.debug('resp data: %(resp)s', {'resp': resp.content})
        return resp.json()


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    output = main()
    if output:
        print(output)
