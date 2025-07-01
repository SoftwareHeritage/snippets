#!/usr/bin/env python

"""
Generate the 1000 most starred repositories from Gtihub's GraphQL results.
Generate "popular1k.json" by
 * opening the GraphQL explorer https://docs.github.com/fr/graphql/overview/explorer
 * log in and authorize
 * enter the query below
 * copy-paste the resulting JSON
 * start this script, redirect it somewhere.

the query:

    query {
        search(query: "stars:>10000", type: REPOSITORY, first: 100) {
            repositoryCount
            edges {
                node {
                    ... on Repository {
                        name
                        owner {
                            login
                        }
                        stargazerCount
                        createdAt
                        url
                    }
                }
            }
        }
    }
"""

from hashlib import sha1
from json import loads

with open("popular1k.json") as input:
    data = loads(input.read())
    repos = []
    for r in data["data"]["search"]["edges"]:
        repo = r["node"]
        repos.append((repo["stargazerCount"], repo["url"]))

repos.sort(key=lambda r: r[0], reverse=True)
for r in repos[0:1000]:
    h = sha1(r[1].encode()).hexdigest()
    print(h, r[0], r[1])
