# Copyright (C) 2021 The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information

import click

from swh.web.client.client import WebAPIClient
from requests.exceptions import HTTPError


@click.command()
@click.argument(
    "origin",
    required=True,
)
@click.pass_context
def main(ctx, origin: str):
    """Retrieve the last swhid for a given origin.

    This is specific to deposit origins whose snapshot only targets one revision named
    HEAD.

    """
    client = WebAPIClient()
    try:
        visit = client.last_visit(origin)
    except HTTPError:
        raise ValueError(f"No origin found matching {origin}")

    try:
        snapshot = next(client.snapshot(visit["snapshot"]))
    except StopIteration:
        raise ValueError(f"No snapshot found for {origin}")

    revision_target = snapshot.get('HEAD', {}).get('target')
    if not revision_target:
        raise ValueError(f"No snapshot matching the deposit pattern for {origin}")
    revision_target_type = snapshot['HEAD']['target_type']
    if revision_target_type != 'revision':
        raise ValueError(f"No snapshot matching the deposit pattern for {origin}")
    revision = client.revision(revision_target)

    if not revision:
        raise ValueError(f"No revision found for {origin}")

    print(revision["directory"])


if __name__ == '__main__':
    main()
