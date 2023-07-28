#!/usr/bin/env python3

__copyright__ = "Copyright (C) 2023 Roberto Di Cosmo"
__license__ = "GPL-3.0-or-later"

#
# Goal: take the URL of an archived repository, and find the SWHID of the directory of the last revision of the main branch of the latest snapshot
#

import click
import requests
import json
from gql import gql, Client
from gql.transport.aiohttp import AIOHTTPTransport

# GraphQL API endpoint
API_URL = "https://archive.softwareheritage.org/graphql/"


def get_dir_latest(url, bearer_token):
    # GraphQL query with parameters for origin URL and number of commits
    query = gql(
        """
    query getOriginEntries($url: String!) {
      origin(url: $url) {
        url
        latestSnapshot {
          swhid
          branches(first: 1, nameInclude: "HEAD") {
            nodes {
              name {
                text
              }
              target {
                resolveChain {
                  text
                }
                node {
                  ...on Revision {
                    swhid
                    directory {
                      swhid
                    }
                  }
                }
              }
            }
          }
        }
      }
    }
    """
    )

    headers = {"Content-Type": "application/json"}
    if bearer_token:
        headers["Authorization"] = "Bearer " + bearer_token
    transport = AIOHTTPTransport(url=API_URL, headers=headers)
    client = Client(
        transport=transport,
        fetch_schema_from_transport=False,
    )
    response = client.execute(query, {"url": url})
    branches = response["origin"]["latestSnapshot"]["branches"]["nodes"]
    if len(branches) < 1 or branches[0]["target"]["node"] is None:
        raise Exception("Unable to identify the main branch for this origin")
    # Extract the SWHIDs of the commits
    directory = branches[0]["target"]["node"]["directory"]
    dir_swhid = directory["swhid"]
    snapshot = response["origin"]["latestSnapshot"]
    snp_swhid = snapshot["swhid"]
    revision = branches[0]["target"]["node"]
    rev_swhid = revision["swhid"]
    # now return
    return (dir_swhid, rev_swhid, snp_swhid)


@click.command()
@click.option(
    "--url", prompt="Software origin URL", help="The URL of the software origin."
)
@click.option(
    "-a",
    "--swh-bearer-token",
    default="",
    metavar="SWHTOKEN",
    show_default=True,
    help="bearer token to bypass SWH API rate limit",
)
@click.option(
    "--nofqid",
    is_flag=True,
    help="Print core directory SWHID instead of fully qualified directory SWHID.",
)
def main(url, swh_bearer_token, nofqid):
    d, r, s = get_dir_latest(url, swh_bearer_token)
    if nofqid:
        print(d)
    else:
        print(f"{d};origin={url};visit={s};anchor={r}")


if __name__ == "__main__":
    main()
