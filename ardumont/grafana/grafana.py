#!/usr/bin/env python3

# This exposes a grafana cli to allow scripting tag edition on a grafana instance.

# This can either use the --url and --token flag to set the necessary authentication. If
# not provided, the cli fallbacks to use a specific configuration file with the
# following format.
#
# $ cat ~/.config/swh/grafana/config.yaml
# grafana:
#   url: https://grafana.softwareheritage.org
#   sa-token: your-grafana-service-account-token
#
# code::
#    ./grafana.py --help
#    Usage: grafana.py [OPTIONS] COMMAND [ARGS]...
#
#      Default api client to manipulate grafana annotations
#
#    Options:
#      --url TEXT    Grafana URL
#      --token TEXT  Grafana service account token
#      --help        Show this message and exit.
#
#    Commands:
#      list-annotations  List current annotations installed in the grafana...
#      set-annotation    Install tags in grafana (output the annotation...
#
# code::
#    $ ./grafana.py set-annotation --message "This is a test" \
#         --tag deployment --tag "environment=test-staging-rke2" | jq .
#    {
#      "id": 30390,
#      "alertId": 0,
#      "alertName": "",
#      "dashboardId": 0,
#      "dashboardUID": null,
#      "panelId": 0,
#      "userId": 0,
#      "newState": "",
#      "prevState": "",
#      "created": 1773136011737,
#      "updated": 1773136011737,
#      "time": 1773136011687,
#      "timeEnd": 1773136011687,
#      "text": "This is a test",
#      "tags": [
#        "deployment",
#        "environment=test-staging-rke2"
#      ],
#      "login": "sa-bot-api-write-for-tags",
#      "email": "sa-bot-api-write-for-tags",
#      "avatarUrl": "/avatar/a486aac9f0f7ed204db66d780505e3b6",
#      "data": {}
#    }

import os
from pathlib import Path
from time import time
from typing import List, Optional

import click
import requests
import yaml

CONFIG_FILEPATH = Path(os.environ["HOME"] + "/.config/swh/grafana/config.yaml")


class ApiClient:
    """Simple API wrapper that keeps a base URL and default headers."""

    def __init__(self, base_url, token=None):
        self.base_url = base_url.rstrip("/")  # ensure no trailing slash
        self.session = requests.Session()  # reuse connections
        # default headers applied to every request
        self.session.headers.update(
            {
                "Accept": "application/json",
                **({"Authorization": f"Bearer {token}"} if token else {}),
            }
        )

    def _url(self, path):
        """Combine base URL with a relative path."""
        return f"{self.base_url}/{path.lstrip('/')}"

    def get(self, path, **kwargs):
        resp = self.session.get(self._url(path), **kwargs)
        resp.raise_for_status()
        return resp

    def post(self, path, json=None, data=None, **kwargs):
        resp = self.session.post(self._url(path), json=json, data=data, **kwargs)
        resp.raise_for_status()
        return resp

    def put(self, path, json=None, **kwargs):
        resp = self.session.put(self._url(path), json=json, **kwargs)
        resp.raise_for_status()
        return resp

    def delete(self, path, **kwargs):
        resp = self.session.delete(self._url(path), **kwargs)
        resp.raise_for_status()
        return resp


class GrafanaApiClient:
    """Grafana api api_client."""

    def __init__(self, base_url, token=None):
        self.api_client = ApiClient(base_url, token=token)

    def get_annotation(self, annotation_id: str):
        return self.api_client.get(f"/api/annotations/{annotation_id}").json()

    def get_annotations(self):
        yield from (t for t in self.api_client.get("/api/annotations").json())

    def post_annotations(self, text: str, tags: List[str]):
        # Create an epoch timestamp of the time of the call (ms)
        now = int(time() * 1000)
        payload = dict(text=text, tags=tags, time=now, timeEnd=now)
        return self.api_client.post("/api/annotations", json=payload)


@click.group()
@click.option("--url", required=False, default=None, help="Grafana URL")
@click.option(
    "--token", required=False, default=None, help="Grafana service account token"
)
@click.pass_context
def cli(ctx, url, token):
    """Default api client to manipulate grafana annotations"""

    ctx.ensure_object(dict)

    config: Optional[dict] = None

    # Read configuration file if any
    if CONFIG_FILEPATH.exists():
        with open(CONFIG_FILEPATH, "r") as f:
            config = yaml.safe_load(f.read())

    if not url and config:
        url = config.get("grafana", {}).get("url", None)

    if not token and config:
        token = config.get("grafana", {}).get("sa-token", None)

    if not url:
        raise ValueError("Grafana url must be set.")

    if not token:
        raise ValueError("Grafana url must be set.")

    ctx.obj["client"] = GrafanaApiClient(url, token=token)


@cli.command()
@click.option(
    "-m",
    "--message",
    help="Message description for the annotation",
)
@click.option(
    "-t",
    "--tag",
    "tags",
    multiple=True,
    help="Tag(s) to install in the grafana instance",
)
@click.pass_context
def set_annotation(ctx, message, tags):
    """Install tags in grafana (output the annotation installed as output)."""
    from json import dumps

    grafana_client = ctx.obj["client"]

    result = grafana_client.post_annotations(message, tags=tags)

    if result.ok:
        annotation_id = result.json()["id"]
        annotation = grafana_client.get_annotation(annotation_id)
        print(dumps(annotation))


@cli.command()
@click.pass_context
def list_annotations(ctx):
    """List current annotations installed in the grafana instance (json output)."""
    from json import dumps

    grafana_client = ctx.obj["client"]
    for annotation in grafana_client.get_annotations():
        print(dumps(annotation))


if __name__ == "__main__":
    cli()
