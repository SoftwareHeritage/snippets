#!/usr/bin/env python3

# Copyright (C) 2025  The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information

import csv
import json
import sys

import click
import requests


@click.command()
@click.option(
    "--sentry-url",
    "-u",
    default="https://sentry.softwareheritage.org",
    show_default=True,
    help="Sentry URL",
    required=True,
)
@click.option(
    "--sentry-token",
    "-t",
    default=None,
    envvar="SENTRY_TOKEN",
    help=(
        "Bearer token required to communicate with Sentry API (can also be provided "
        "in SENTRY_TOKEN environment variable)"
    ),
    required=True,
)
@click.option(
    "--sentry-issue-number",
    "-i",
    help="Sentry issue number to extract celery task parameters",
    required=True,
)
@click.option(
    "--environment",
    "-e",
    default="",
    help="Filter on environment: production or staging, both are selected by default",
    required=True,
)
@click.argument("task_type", nargs=1, required=True)
def run(sentry_url, sentry_token, sentry_issue_number, environment, task_type):
    """Extract celery task parameters from a Sentry issue related to a Software Heritage
    loader and dumps a CSV file to stdout that can be consumed by the CLI command :
    swh scheduler task schedule --columns type --columns kwargs <csv_file>."""

    sentry_api_base_url = f"{sentry_url.rstrip('/')}/api/0"
    sentry_issue_events_url = (
        f"{sentry_api_base_url}/issues/{sentry_issue_number}/events/?full=true"
    )

    auth_header = {"Authorization": f"Bearer {sentry_token}"}

    task_params = {}

    csv_writer = csv.writer(sys.stdout)

    while True:
        response = requests.get(sentry_issue_events_url, headers=auth_header)
        events = response.json()
        if not events:
            break
        for event in events:
            task_param = event.get("context", {}).get("celery-job", {}).get("kwargs")
            if task_param:
                task_params[tuple(task_param.values())] = task_param

        sentry_issue_events_url = response.links.get("next", {}).get("url")

    for task_param in task_params.values():
        csv_writer.writerow([task_type, json.dumps(task_param)])


if __name__ == "__main__":
    run()
