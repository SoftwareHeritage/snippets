#!/usr/bin/env python3

# Copyright (C) 2023  The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information

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
    help="Sentry issue number to extract origin URLs",
    required=True,
)
@click.option(
    "--environment",
    "-e",
    default="",
    help="Filter on environment: production or staging, both are selected by default",
    required=True,
)
def run(sentry_url, sentry_token, sentry_issue_number, environment):
    """Extract origin URLs from a Sentry issue related to a Software Heritage
    loader and dumps them to stdout."""

    sentry_api_base_url = f"{sentry_url.rstrip('/')}/api/0"
    sentry_issue_events_url = (
        f"{sentry_api_base_url}/issues/{sentry_issue_number}/events/"
    )

    auth_header = {"Authorization": f"Bearer {sentry_token}"}
    origin_urls = set()

    while True:
        response = requests.get(sentry_issue_events_url, headers=auth_header)
        events = response.json()
        if not events:
            break
        for event in events:
            tags = {tag["key"]: tag["value"] for tag in event.get("tags", [])}
            env_match = environment in tags.get("environment", "")
            if "swh.loader.origin_url" in tags and env_match:
                origin_urls.add(tags["swh.loader.origin_url"])

        sentry_issue_events_url = response.links.get("next", {}).get("url")

    for origin_url in origin_urls:
        print(origin_url)


if __name__ == "__main__":
    run()
