#!/usr/bin/env python3

__copyright__ = "Copyright (C) 2023 Roberto Di Cosmo"
__license__ = "GPL-3.0-or-later"

#
# Goal: take the URL of an archived repository, and find the SWHID of the directory of the last revision of the main branch of the latest snapshot
#

import click
import requests
import json

def get_dir_latest(origin_url):
    # GraphQL API endpoint
    url = "https://archive.softwareheritage.org/graphql/"

    # GraphQL query with parameters for origin URL and number of commits
    query = f"""
         query getOriginEntries {{
           origin(url: "{origin_url}") {{
             url
             latestVisit(requireSnapshot: true) {{
               date
               latestStatus(requireSnapshot: true, allowedStatuses: [full]) {{
                 snapshot {{
                   swhid
                   branches(first: 1, types: [revision]) {{
                     pageInfo {{
                       endCursor
                       hasNextPage
                     }}
                     nodes {{
                       name {{
                         text
                       }}
                       target {{
                         type
                         node {{
                           ... on Revision {{
                             swhid
                             directory {{
                               swhid
                             }}
                           }}
                         }}
                       }}
                     }}
                   }}
                 }}
               }}
             }}
           }}
         }}     
    """

    # Headers
    headers = {"Content-Type": "application/json"}

    # Request payload
    payload = {"query": query}

    # Send the POST request
    response = requests.post(url, headers=headers, data=json.dumps(payload))

    # Parse the JSON response
    data = response.json()

    # Extract the SWHIDs of the commits
    directory = data["data"]["origin"]["latestVisit"]["latestStatus"]["snapshot"]["branches"]["nodes"][0]["target"]["node"]["directory"]
    swhid = directory["swhid"]

    return swhid

# now return 

@click.command()
@click.option('--url', prompt='Software origin URL', help='The URL of the software origin.')

def main(url):
    print(get_dir_latest(url))

if __name__ == '__main__':
    main()
