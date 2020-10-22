#!/usr/bin/env python3

"""list all SourceForge project "tools", starting from a project list

output format is a list of records, each consisting of TAB-separated fields:
project_name, tool_name, tool_url

Example:

    $ shuf sourceforge-projects.txt | sourceforge-ls-tools - > sourceforge-tools.csv

"""

__copyright__ = "Copyright (C) 2020  Stefano Zacchiroli"
__license__ = "GPL-3.0-or-later"


import click
import logging

from concurrent.futures import ThreadPoolExecutor
from requests_futures.sessions import FuturesSession
from tqdm import tqdm


SF_BASE_URL = "https://sourceforge.net"
REST_URL_PREFIX = "https://sourceforge.net/rest/p/"
WORKERS = 8


def ls_all_tools(projects):
    session = FuturesSession(executor=ThreadPoolExecutor(max_workers=WORKERS))
    responses = []

    for project in projects:  # schedule requests
        rest_url = REST_URL_PREFIX + project
        responses.append((project, session.get(rest_url)))

    for proj_name, res in tqdm(responses):  # extract tools from responses
        try:
            for tool in res.result().json()["tools"]:
                print(proj_name, tool["name"], SF_BASE_URL + tool["url"], sep="\t")
        except Exception as err:
            logging.error(f"cannot list tools for project {proj_name}: {err}")


@click.command()
@click.argument("project_list", type=click.File())
def main(project_list):
    logging.basicConfig(level=logging.INFO, filename="sourceforge-tools.log")
    ls_all_tools([line.rstrip() for line in project_list])


if __name__ == "__main__":
    main()
