# Copyright (C) 2020-2022 The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information

import os

import click
import requests
from typing import Iterator

SENTRY_API_BASE_URL = "https://sentry.softwareheritage.org/api/0"


def stream_urls(event_id: str, project_name: str) -> Iterator[str]:
    sentry_issue_events_url = f"{SENTRY_API_BASE_URL}/issues/{event_id}/events/"
    sentry_api_token = os.environ["SENTRY_TOKEN"]
    auth_header = {"Authorization": f"Bearer {sentry_api_token}"}

    while sentry_issue_events_url:
        response = requests.get(sentry_issue_events_url, headers=auth_header)
        events = response.json()
        if not events:
            break
        for event in events:
            sentry_event_data_url = f"{SENTRY_API_BASE_URL}/projects/swh/{project_name}/events/{event['eventID']}/"
            sentry_event_data = requests.get(
                sentry_event_data_url, headers=auth_header
            ).json()

            yield sentry_event_data["context"]["celery-job"]["kwargs"]["url"]
            sentry_issue_events_url = response.links.get("next", {}).get("url")


@click.command()
@click.option("-i", "--event-id", help="Event id, e.g. 5823")
@click.option(
    "-p", "--project-name", help="Associated project name, e.g. swh-loader-git"
)
def main(event_id: str, project_name: str) -> None:
    origin_urls = set()

    for origin_url in stream_urls(event_id, project_name):
        if origin_url in origin_urls:
            continue
        origin_urls.add(origin_url)
        print(origin_url)


if __name__ == "__main__":
    main()
