#!/usr/bin/env python

"""
Generate the 1000 most starred repositories from Github's GraphQL results.

Needs a token in the GITHUB_TOKEN env variable. If you don't have one yet:
 * create a classic access token https://github.com/settings/tokens/new
 * authorize public_repo

hints:
 * initial query source: https://www.reddit.com/r/github/comments/1hx7iej/comment/m67yp2o/
 * GraphQL explorer https://docs.github.com/fr/graphql/overview/explorer
 * https://docs.github.com/fr/graphql/guides/using-pagination-in-the-graphql-api
"""

from json import dumps
from hashlib import sha1
from os import environ

import requests

TOKEN = environ["GITHUB_TOKEN"]

def post(end_cursor=None):
    after = ''
    if end_cursor:
        after = f', after: "{end_cursor}"'
    query = """query {
        search(query: "stars:>10000", type: REPOSITORY, first: 100 %s) {
            repositoryCount
            edges {
                node {
                    ... on Repository {
                        stargazerCount
                        url
                    }
                }
            }
            pageInfo {
                endCursor
                hasNextPage
            }
        }
    }""" % (after)
    res = requests.post("https://api.github.com/graphql",
        headers= {"Authorization": f"Bearer {TOKEN}"},
        data=dumps({"query": query}),
    )
    data = res.json()
    # print(data)
    return data

repos = []
data = post()
while data:
    search = data["data"]["search"]
    for r in search["edges"]:
        repo = r["node"]
        repos.append((repo["stargazerCount"], repo["url"]))
    if search["pageInfo"]["hasNextPage"]:
        data = post(end_cursor=search["pageInfo"]["endCursor"])
    else:
        data = None

repos.sort(key=lambda r: r[0], reverse=True)
for r in repos[0:1000]:
    h = sha1(r[1].encode()).hexdigest()
    print(h, r[0], r[1])
