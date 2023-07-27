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

API_URL = "https://archive.softwareheritage.org/graphql/"


def get_dir_latest(url, bearer_token):
    # GraphQL API endpoint
    # GraphQL query with parameters for origin URL and number of commits
    query = gql("""
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
    """)

    headers = {"Content-Type": "application/json"}
    if (bearer_token):
        headers["Authorization"] = "Bearer " + bearer_token
    transport = AIOHTTPTransport(
        url=API_URL,
        headers=headers
    )
    client = Client(
        transport=transport,
        fetch_schema_from_transport=False,
    )
    response = client.execute(query, {"url": url})
    # Extract the SWHIDs of the commits
    branches = response["origin"]["latestSnapshot"]["branches"]["nodes"]
    if len(branches) < 1:
        print("Unable to identify the main branch for this origin")
        return None
    else:
        directory = response["origin"]["latestSnapshot"]["branches"]["nodes"][0]["target"]["node"]["directory"]
        swhid = directory["swhid"]
        return swhid

# now return

@click.command()
@click.option('--url', prompt='Software origin URL', help='The URL of the software origin.')
@click.option(
    "-a",
    "--swh-bearer-token",
    default="",
    metavar="SWHTOKEN",
    show_default=True,
    help="bearer token to bypass SWH API rate limit",
)
def main(url,swh_bearer_token):
    print(get_dir_latest(url,swh_bearer_token))

if __name__ == '__main__':
    main()
