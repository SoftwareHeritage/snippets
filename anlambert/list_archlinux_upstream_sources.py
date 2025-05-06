#!/usr/bin/env python3

# Copyright (C) 2025  The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information

import json
import os
import re
import string
import subprocess
import tempfile

import click
import requests
from srcinfo.parse import parse_srcinfo

from anlambert_utils import url_get, clone_repository

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


def get_package_srcinfo_from_gitlab_api(package):
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
            srcinfo_src = ""
        else:
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
    return srcinfo_src


def get_package_srcinfo_from_git(package):
    with tempfile.TemporaryDirectory() as tmpdir:
        try:
            clone_repository(package["http_url_to_repo"], tmpdir)
        except ValueError:
            # empty repository
            return ""
        srcinfo_path = os.path.join(tmpdir, ".SRCINFO")
        pkgbuild_path = os.path.join(tmpdir, "PKGBUILD")
        if os.path.exists(srcinfo_path):
            with open(srcinfo_path, "r") as srcinfo_src:
                return srcinfo_src.read()
        elif os.path.exists(pkgbuild_path):
            # requires pacman-package-manager package installed on debian
            return subprocess.check_output(
                ["makepkg", "--printsrcinfo"], cwd=tmpdir, text=True, encoding="utf-8"
            )
        else:
            return ""


@click.command()
@click.option(
    "--srcinfo-from-git",
    "-g",
    default=False,
    is_flag=True,
    show_default=True,
    help=(
        "Clone each ArchLinux package repository to process source info "
        "instead of fetching .SRCINFO and PKGBUILD files from GitLab API"
    ),
)
@click.option(
    "--start-after-name",
    "-a",
    default="",
    show_default=True,
    help=("Only process packages whose name is greater than the provided string"),
)
def run(srcinfo_from_git, start_after_name):
    """Iterate on all ArchLinux official packages, extract upstream
    sources information and dump NDJSON to stdout."""

    page_response = url_get(ARCHLINUX_LIST_PACKAGES_URL)
    packages = page_response.json()

    while packages:
        for package in packages:
            if package["name"] < start_after_name:
                continue
            if srcinfo_from_git:
                srcinfo_src = get_package_srcinfo_from_git(package)
            else:
                srcinfo_src = get_package_srcinfo_from_gitlab_api(package)

            if not srcinfo_src:
                continue

            srcinfo = parse_srcinfo(srcinfo_src)[0]
            if "source" not in srcinfo:
                continue

            package_srcinfo = {
                "origin_url": package["web_url"],
                "source": srcinfo["source"],
            }
            # recipes for computing source checksums according to its type (bzr, hg,
            # git or file) can be found in the pacman repository:
            # https://gitlab.archlinux.org/pacman/pacman/-/tree/master/scripts/libmakepkg/source
            for checksums in ("sha256sums", "sha512sums", "b2sums", "md5sums"):
                if checksums in srcinfo:
                    package_srcinfo[checksums] = srcinfo[checksums]
            print(json.dumps(package_srcinfo))

        if "next" in page_response.links:
            page_response = url_get(page_response.links["next"]["url"])
            packages = page_response.json()
        else:
            packages = None


if __name__ == "__main__":
    run()
