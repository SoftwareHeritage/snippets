#!/usr/bin/env python3

# Copyright (C) 2025  The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information

# Simple script to identify bogus extids associated to hg-checkout visits
# as associated loader was archiving .hg folders after first deployment

import json
import os
import string

import logging
import re
import requests
import subprocess
import tempfile

from srcinfo.parse import parse_srcinfo
from tenacity.before_sleep import before_sleep_log

from swh.core.retry import http_retry

ARCHLINUX_GITLAB_API_URL = "https://gitlab.archlinux.org/api/v4"

ARCHLINUX_LIST_PACKAGES_URL = (
    f"{ARCHLINUX_GITLAB_API_URL}/projects?"
    "search=archlinux+packaging+packages&"
    "search_namespaces=true&"
    "order_by=name&sort=asc&"
    "per_page=100"
)

ARCHLINUX_PACKAGE_FILE_URL = string.Template(
    f"{ARCHLINUX_GITLAB_API_URL}/projects/$project_id/"
    "repository/files/$file/raw?ref=$ref"
)

logger = logging.getLogger(os.path.basename(__file__))
session = requests.Session()


@http_retry(before_sleep=before_sleep_log(logger, logging.WARNING))
def url_get(url):
    response = session.get(url)
    response.raise_for_status()
    return response


# Iterate on all archlinux official packages, extract upstream
# sources information and dump NDJSON to stdout

page_response = url_get(ARCHLINUX_LIST_PACKAGES_URL)
packages = page_response.json()

while packages:
    for package in packages:
        srcinfo_url = ARCHLINUX_PACKAGE_FILE_URL.substitute(
            project_id=package["id"], file=".SRCINFO", ref="HEAD"
        )
        try:
            srcinfo_src = url_get(srcinfo_url).text
        except requests.HTTPError:
            pkgbuild_url = ARCHLINUX_PACKAGE_FILE_URL.substitute(
                project_id=package["id"], file="PKGBUILD", ref="HEAD"
            )
            try:
                pkgbuild_response = url_get(pkgbuild_url)
            except requests.HTTPError:
                continue

            with tempfile.TemporaryDirectory() as tmpdir:
                pkgbuild_path = os.path.join(tmpdir, "PKGBUILD")
                with open(pkgbuild_path, "w") as pkgbuild:
                    # remove 'install=<package>.install' variable in PKGBUILD file
                    # or makepkg will fail otherwise
                    clean_pkgbuild = re.sub(
                        r"^[ \t]*install=.*\.install.*$",
                        "",
                        pkgbuild_response.text,
                        flags=re.MULTILINE,
                    )
                    pkgbuild.write(clean_pkgbuild)
                # requires pacman-package-manager package installed on debian
                srcinfo_src = subprocess.check_output(
                    ["makepkg", "--printsrcinfo"], cwd=tmpdir
                ).decode()

        srcinfo = parse_srcinfo(srcinfo_src)[0]
        if "source" not in srcinfo:
            continue

        package_srcinfo = {
            "origin_url": package["web_url"],
            "source": srcinfo["source"],
        }
        for checksums in ("sha256sums", "sha512sums", "b2sums"):
            if checksums in srcinfo:
                package_srcinfo[checksums] = srcinfo[checksums]
        print(json.dumps(package_srcinfo))

    page_response = url_get(page_response.links["next"]["url"])
    packages = page_response.json()
