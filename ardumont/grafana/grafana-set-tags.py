#!/usr/bin/env python3

import os
from pathlib import Path
from time import time
from typing import Optional

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


class GrafanaApiClient(ApiClient):
    """Grafana api client."""

    def get_annotation(self, annotation_id):
        return self.get(f"/api/annotations/{annotation_id}").json()

    def get_annotations(self):
        yield from (t for t in self.get("/api/annotations").json())

    def post_annotations(self, text, tags):
        # Create an epoch timestamp of the time of the call (ms)
        now = int(time() * 1000)
        payload = dict(text=text, tags=tags, time=now, timeEnd=now)
        return self.post("/api/annotations", json=payload)


@click.group()
@click.option("--url", required=False, default=None, help="Grafana URL")
@click.option(
    "--token", required=False, default=None, help="Grafana service account token"
)
@click.pass_context
def cli(ctx, url, token):
    """Default client to manipulate grafana annotations"""

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
@click.pass_context
def main(ctx):
    """Manipulate grafana to install tags"""
    from pprint import pprint

    client = ctx.obj["client"]

    result = client.post_annotations(
        "This is a scripted test", tags=["deployment", "test", "ok"]
    )

    if result.ok:
        annotation_id = result.json()["id"]
        annotation = client.get_annotation(annotation_id)
        pprint(annotation)
    else:
        for annotation in client.get_annotations():
            pprint(annotation)


if __name__ == "__main__":
    cli()
