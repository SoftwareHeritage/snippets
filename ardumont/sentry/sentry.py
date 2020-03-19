#!/usr/bin/env python3

import json
import logging

import click
import requests

from typing import Any, Dict


logger = logging.getLogger(__name__)


SENTRY_URL = 'https://sentry.softwareheritage.org'


def url_api_project(base_url: str) -> str:
    return f'{base_url}/api/0/projects/'


def url_api_token(base_url: str) -> str:
    return f'{base_url}/settings/account/api/auth-tokens/'


@click.group()
@click.option('-a', '--api-url', default=SENTRY_URL, help='sentry api to use')
@click.option('-t', '--token', help='Api authentication token')
@click.pass_context
def main(ctx, api_url: str, token: str):
    """Allow sentry data manipulation with the click

    """
    api_token = url_api_token(api_url)
    if not token:
        raise ValueError(
            f'Missing api token, connect and generate one in {api_token}'
        )
    ctx.ensure_object(dict)
    ctx.obj['token'] = token
    ctx.obj['url'] = {
        'base': api_url,
        'project': url_api_project(api_url),
        'api-token': api_token,
    }


@main.command('project')
@click.pass_context
def list_projects(ctx: Dict) -> Dict[str, Any]:
    """List all projects's. This returns a mapping from their name to their id.

    """
    url = ctx.obj['url']['project']
    token = ctx.obj['token']
    resp = requests.get(url, headers={
        'Authorization': f'Bearer {token}',
        'content-type': 'application/json'
    })

    if resp.ok:
        logger.debug('resp: %(resp)s', {'resp': resp})
        data = resp.json()
        projects = {}
        for project in data:
            projects[project['name']] = project['id']
        click.echo(json.dumps(projects))


if __name__ == '__main__':
    # logging.basicConfig(level=logging.DEBUG)
    main()
