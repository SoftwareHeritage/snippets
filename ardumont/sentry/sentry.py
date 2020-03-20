# Copyright (C) 2020 The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information

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


def url_issue_events(base_url: str, issue_id: int) -> str:
    return f'{base_url}/api/0/issues/{issue_id}/events/'


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


def query(url, token: Optional[str] = None) -> Dict[str, Any]:
    """Query the sentry api url with authentication token.
       This returns result per page.

    """
    resp = requests.get(url, headers={
        'Authorization': f'Bearer {token}',
        'content-type': 'application/json'
    })

    if resp.ok:
        logger.debug('resp: %(resp)s', {'resp': resp})
        data = resp.json()

        if 'next' in resp.links:
            next_page = resp.links['next']['url']
        else:
            next_page = None
        return {'data': data, 'next': next_page}
    return {'data': None, 'next': None}


def query_all(url, token: Optional[str] = None):
    """Query api which resolves the pagination

    """
    while True:
        data = query(url, token=token)
        if not data['data']:
            break
        yield data['data']
        if not data['next']:
            break
        url = data['next']


@main.command('project')
@click.pass_context
def list_projects(ctx: Dict) -> Dict[str, Any]:
    """List all projects's. This returns a mapping from their slug to their {id,
    name}.

    """
    url = ctx.obj['url']['project']
    token = ctx.obj['token']
    page_projects = query_all(url, token=token)
    mappings = {}
    for projects in page_projects:
        for project in projects:
            mappings[project['slug']] = {
                'id': project['id'],
                'name': project['name'],
            }
    click.echo(json.dumps(mappings))


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
    data = query_all(url, token=token)

    mappings = {}
    for issues in data:
        for issue in issues:
            mappings[issue['id']] = {
                'short-id': issue['shortId'],
                'status': issue['status'],
                'metadata': issue['metadata'],
            }

    click.echo(json.dumps(mappings))


@main.command('issue')
@click.option('--issue-id', '-i', help='Issue id (not the short one listed in ui)')
@click.pass_context
def issue(ctx, issue_id):
    """Get detail about a specific issue by its id.

    """
    base_url = ctx.obj['url']['base']
    token = ctx.obj['token']

    url = url_issue(base_url, issue_id)
    data = query(url, token=token)

    issue = data['data']
    if data:
        summary_issue = {
            'short-id': issue['shortId'],
            'title': issue['title'],
            'first-seen': issue['firstSeen'],
            'last-seen': issue['lastSeen'],
            'count': issue['count'],
            'status': issue['status'],
            'project': issue['project']['slug'],
            'culprit': issue['culprit'],
            'metadata': issue['metadata'],
        }
        click.echo(json.dumps(summary_issue))


@main.command('events')
@click.option('--issue-id', '-i', help='Issue id (not the short one listed in ui)')
@click.pass_context
def events(ctx, issue_id):
    """Get detail about a specific issue by its id.

    """
    base_url = ctx.obj['url']['base']
    token = ctx.obj['token']

    url = url_issue_events(base_url, issue_id)
    data = query_all(url, token=token)

    mappings = {}
    for events in data:
        for event in events:
            mappings[event['id']] = {
                'culprit': event['culprit'],
                'title': event['title'],
                'message': event['message'],
                'project-id': event['projectID'],
                'group-id': event['groupID'],
            }
    click.echo(json.dumps(mappings))


if __name__ == '__main__':
    # logging.basicConfig(level=logging.DEBUG)
    main()
