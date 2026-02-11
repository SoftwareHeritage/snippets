#!/usr/bin/env python3

# Copyright (C) 2026  The Software Heritage developers
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information

# Script to disambiguate between instances of Gitea forges and Forgejo forges.
#
# With a file holding the necessary information:
# psql service=staging-swh-web -At \
#   -c "select forge_url from add_forge_request where forge_type = 'gitea'
#       order by forge_url" > gitea-forges.staging.txt
#
# Then:
# cat gitea-forges.staging.txt | ./identify_forgejo_instances.py --environment staging
# Or for production
# cat gitea-forges.production.txt | \
#   ./identify_forgejo_instances.py --environment production

# This can also generate the necessary update queries to execute in both scheduler or
# web db (in transaction for further checks prior to actually commit those).

# Usage: identify_forgejo_instances.py [OPTIONS]
# Options:
#   --force                         Force generation even if generation output
#                                   already exists
#   -e, --environment [staging|production]
#                                   Environment and eponym directory to generate
#                                   the output data to.
#   --with-sql-update-scheduler     Flag to generate the db scheduler update sql
#                                   file.
#   --with-sql-update-web           Flag to generate the db web update sql file.
#   --help                          Show this message and exit.

import json
import os
import os.path
import sys
from io import BytesIO
from urllib.parse import urlparse

import certifi
import click
import pycurl
from anubis_solver import solve

forgejo_urls = set()
gitea_urls = set()
dead_urls = set()
http_error_urls = set()
no_json_response_urls = set()
auth_needed_forge_urls = set()
anubis_protected_forge_urls = set()


def fetch_url_with_curl(url, cookie=None):
    buffer = BytesIO()
    c = pycurl.Curl()
    c.setopt(c.URL, url)
    c.setopt(c.USERAGENT, "curl/8.5.0")
    c.setopt(c.WRITEDATA, buffer)
    c.setopt(c.CAINFO, certifi.where())
    c.setopt(c.FOLLOWLOCATION, True)
    c.setopt(c.TIMEOUT, 3)
    # c.setopt(c.VERBOSE, True)
    if cookie:
        c.setopt(c.COOKIE, cookie)
    c.perform()
    status_code = c.getinfo(c.RESPONSE_CODE)
    c.close()
    buffer.seek(0)

    return buffer.read().decode(), status_code


# for some reasons I did not understand yet, some challenge cannot be resolved
# using requests so we use curl instead to send the solve request (aligning
# request headers with those sent by curl when using requests was tested but
# it did not help to resolve the challenge)
def resolve_anubis_with_curl(url: str) -> tuple[str, int]:
    parsed_url = urlparse(url)
    base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
    path_split = parsed_url.path.lstrip("/").split("/")

    # anubis solve URL must be rooted to the forge home URL
    # so we try combinations of URL sub-paths until finding
    # the right one
    solve_url = base_url
    for sub_path in path_split:
        try:
            return fetch_url_with_curl(url, cookie=solve(solve_url))
        except Exception:
            solve_url += f"/{sub_path}"
            pass

    print(f"Could not resolve anubis challenge for URL {url}", file=sys.stderr)
    return "", 0


def fetch_url(url: str, forge_url: str | None = None) -> tuple[str, int]:
    try:
        response, status_code = fetch_url_with_curl(url)
    except Exception:
        print(f"Error when fetching {url}", file=sys.stderr)
        dead_urls.add(url)
        return "", 0

    if status_code == 200 and "anubis" in response:
        # URL is protected by anubis, try to solve challenge and retry request
        anubis_protected_forge_urls.add(forge_url or url)
        print(
            f"URL {url} is protected by anubis, computing cookie",
            file=sys.stderr,
        )
        return resolve_anubis_with_curl(url)

    return response, status_code


@click.command()
@click.option(
    "--force",
    is_flag=True,
    default=False,
    help="Force generation even if generation output already exists",
)
@click.option(
    "-e",
    "--environment",
    "environment_dir",
    default="staging",
    type=click.Choice(["staging", "production"]),
    help="Environment and eponym directory to generate the output data to.",
)
@click.option(
    "--with-sql-update-scheduler",
    is_flag=True,
    default=False,
    help="Flag to generate the db scheduler update sql file.",
)
@click.option(
    "--with-sql-update-web",
    is_flag=True,
    default=False,
    help="Flag to generate the db web update sql file.",
)
def main(environment_dir, force, with_sql_update_scheduler, with_sql_update_web):
    # Create the local environment directory where we will write the output data files
    os.makedirs(environment_dir, exist_ok=True)

    forgejo_urls = set()
    forgejo_urls_path = environment_dir + "/forgejo_urls"

    if force or not os.path.exists(forgejo_urls_path):
        # iterate on forge URLs to disambiguate between gitea and forgejo
        for forge_url in map(lambda s: s.rstrip("\n/"), sys.stdin):
            api_url = forge_url + "/api/v1/version"

            # try using forge version from REST API first
            response, status_code = fetch_url(api_url, forge_url)

            if status_code == 200:
                try:
                    # gitea version number starts with 1. or v1., can also occasionally
                    # be a short commit hash
                    forge_version = json.loads(response)["version"]
                    if (
                        forge_version.startswith(("1.", "v1."))
                        or "." not in forge_version
                    ):
                        gitea_urls.add(forge_url)
                    else:
                        forgejo_urls.add(forge_url)
                except Exception:
                    no_json_response_urls.add(forge_url)
                    print(
                        f"Could not decode JSON response from {api_url}",
                        file=sys.stderr,
                    )
            elif status_code == 403:
                # forge API requires authentication, scrape forge homepage then
                auth_needed_forge_urls.add(forge_url)
                response, status_code = fetch_url(forge_url)

                # disambiguate between gitea and forgejo
                if status_code == 200 and "Powered by Forgejo" in response:
                    forgejo_urls.add(forge_url)
                elif status_code == 200 and (
                    "Powered by Gitea" in response or "docs.gitea" in response
                ):
                    gitea_urls.add(forge_url)
                elif status_code == 200:
                    print(
                        f"Could not determine forge type for URL {forge_url}",
                        file=sys.stderr,
                    )
                elif status_code != 200:
                    http_error_urls.add(f"{forge_url}, {status_code}")
                    print(
                        f"Error when fetching {forge_url}: {status_code}",
                        file=sys.stderr,
                    )
            elif status_code:
                http_error_urls.add(f"{forge_url}, {status_code}")
                print(
                    f"Error when fetching {forge_url}: {status_code}", file=sys.stderr
                )

        # Start writing the data output files
        with open(forgejo_urls_path, "w") as f:
            f.write("\n".join(sorted(forgejo_urls)))

        with open(environment_dir + "/gitea_urls", "w") as f:
            f.write("\n".join(sorted(gitea_urls)))

        with open(environment_dir + "/dead_forge_urls", "w") as f:
            f.write("\n".join(sorted(dead_urls)))

        with open(environment_dir + "/http_error_forge_urls", "w") as f:
            f.write("\n".join(sorted(http_error_urls)))

        with open(environment_dir + "/auth_needed_forge_urls", "w") as f:
            f.write("\n".join(sorted(auth_needed_forge_urls)))

        with open(environment_dir + "/anubis_protected_forge_urls", "w") as f:
            f.write("\n".join(sorted(anubis_protected_forge_urls)))

    # We bypass the generation, let's read the file holding the forgejo urls to migrate
    if not forgejo_urls and os.path.exists(forgejo_urls_path):
        with open(forgejo_urls_path, "r") as f:
            forgejo_urls = set([url.rstrip("\n") for url in f.readlines()])

    if with_sql_update_scheduler:
        if not forgejo_urls:
            raise ValueError(f"<{forgejo_urls}> should not be empty!")

        with open(environment_dir + "/sql_update_scheduler.sql", "w") as sql_sched_f:
            for url in forgejo_urls:
                instance = urlparse(url).netloc
                row_sql_update = """
update listers
set name='forgejo'
where name='gitea' and instance_name='%s';

update task set type='list-forgejo-full'
where type='list-gitea-full' and
      (arguments#>>'{kwargs,instance}'='%s' or arguments#>>'{kwargs,url}'='%s');

"""
                sql_sched_f.write(row_sql_update % (instance, instance, url))

    if with_sql_update_web:
        if not forgejo_urls:
            raise ValueError(f"<{forgejo_urls}> should not be empty!")

        with open(environment_dir + "/sql_update_web.sql", "w") as sql_web_f:
            for url in forgejo_urls:
                row_sql_update = f"""
update add_forge_request
set forge_type='forgejo'
where forge_type='gitea' and forge_url='{url}/';

"""
                sql_web_f.write(row_sql_update)


if __name__ == "__main__":
    main()
