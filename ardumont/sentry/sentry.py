#!/usr/bin/env python3

import json
import logging

import click
import requests

from typing import Any, Dict, Optional, Iterable


logger = logging.getLogger(__name__)


SENTRY_URL = 'https://sentry.softwareheritage.org'
ORGA_SLUG = 'swh'


def url_api_project(base_url: str) -> str:
    return f'{base_url}/api/0/projects/'


def url_api_token(base_url: str) -> str:
    return f'{base_url}/settings/account/api/auth-tokens/'


def url_project_issues(base_url: str, project_slug: str, short_id: Optional[str] = None) -> str:
    return f'{base_url}/api/0/projects/{ORGA_SLUG}/{project_slug}/issues/'


def url_issue(base_url: str, issue_id: int) -> str:
    return f'{base_url}/api/0/issues/{issue_id}/'


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


def project_name_to_id(projects: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    """Compute the project mapping from name to id.

    """
    mapping = {}
    for project in projects:
        mapping[project['slug']] = {
            'id': project['id'],
            'name': project['name'],
        }
    return mapping


def query(url, token: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Query the sentry api url with authentication token.

    """
    resp = requests.get(url, headers={
        'Authorization': f'Bearer {token}',
        'content-type': 'application/json'
    })

    if resp.ok:
        logger.debug('resp: %(resp)s', {'resp': resp})
        data = resp.json()
        return data


@main.command('project')
@click.pass_context
def list_projects(ctx: Dict) -> Dict[str, Any]:
    """List all projects's. This returns a mapping from their slug to their {id,
    name}.

    """
    url = ctx.obj['url']['project']
    token = ctx.obj['token']
    data = query(url, token=token)
    if data:
        projects = project_name_to_id(data)
        click.echo(json.dumps(projects))


@main.command('issues')
@click.option('--project-slug', '-p', required=1,
               help="Project's slug identifier")
@click.pass_context
def issues(ctx, project_slug):
    """List all projects's issues. This returns a mapping from their id to their
    summary.

    """
    base_url = ctx.obj['url']['base']
    token = ctx.obj['token']

    url = url_project_issues(base_url, project_slug)
    data = query(url, token=token)

    if data:
        mappings = {}
        for issue in data:
            mappings[issue['id']] = {
                'short-id': issue['shortId'],
                'status': issue['status'],
                'metadata': issue['metadata'],
            }

        click.echo(json.dumps(mappings))


if __name__ == '__main__':
    # logging.basicConfig(level=logging.DEBUG)
    main()
