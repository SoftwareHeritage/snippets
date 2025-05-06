#!/usr/bin/env python3

# Copyright (C) 2025  The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information

import json
import os
import shutil
import subprocess
import tempfile

import click
from srcinfo.parse import parse_srcinfo

from anlambert_utils import url_get, clone_repository

AUR_BASE_URL = "https://aur.archlinux.org"

AUR_PACKAGES_INDEX_URL = f"{AUR_BASE_URL}/packages-meta-v1.json.gz"

AUR_PACKAGE_BASE_SNAPSHOT_URL = f"{AUR_BASE_URL}/cgit/aur.git/snapshot"


def get_package_srcinfo(package_path):
    srcinfo_path = os.path.join(package_path, ".SRCINFO")
    pkgbuild_path = os.path.join(package_path, "PKGBUILD")
    if os.path.exists(srcinfo_path):
        with open(srcinfo_path, "r") as srcinfo_src:
            return srcinfo_src.read()
    elif os.path.exists(pkgbuild_path):
        # requires pacman-package-manager package installed on debian
        return subprocess.check_output(
            ["makepkg", "--printsrcinfo"], cwd=package_path, text=True, encoding="utf-8"
        )
    else:
        return ""


def get_package_srcinfo_from_snapshot(package):
    response = url_get(
        f"{AUR_PACKAGE_BASE_SNAPSHOT_URL}/{package['PackageBase']}.tar.gz"
    )
    with tempfile.TemporaryDirectory() as tmpdir:
        archive_path = os.path.join(tmpdir, "snapshot.tar.gz")
        with open(archive_path, "wb") as archive:
            archive.write(response.content)
        extract_path = os.path.join(tmpdir, "snapshot")
        shutil.unpack_archive(archive_path, extract_path)
        package_path = os.path.join(extract_path, package["PackageBase"])
        return get_package_srcinfo(package_path)


def get_package_srcinfo_from_git(package):
    repo_url = f"{AUR_BASE_URL}/{package['PackageBase']}.git"
    with tempfile.TemporaryDirectory() as tmpdir:
        try:
            clone_repository(repo_url, tmpdir)
        except ValueError:
            # empty repository
            return ""
        return get_package_srcinfo(tmpdir)


@click.command()
@click.option(
    "--srcinfo-from-git",
    "-g",
    default=False,
    is_flag=True,
    show_default=True,
    help=(
        "Clone each AUR package repository to process source info "
        "instead of fetching .SRCINFO and PKGBUILD files from latest snapshot"
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
    """Iterate on all AUR official packages, extract upstream
    sources information and dump NDJSON to stdout."""

    response = url_get(AUR_PACKAGES_INDEX_URL)

    processed_packages = set()

    for package in response.json():
        if (
            package["PackageBase"] in processed_packages
            or package["Name"] < start_after_name
        ):
            continue

        processed_packages.add(package["PackageBase"])

        if srcinfo_from_git:
            srcinfo_src = get_package_srcinfo_from_git(package)
        else:
            srcinfo_src = get_package_srcinfo_from_snapshot(package)

        if not srcinfo_src:
            continue

        srcinfo = parse_srcinfo(srcinfo_src)[0]
        if "source" not in srcinfo:
            continue

        package_srcinfo = {
            "origin_url": f"{AUR_BASE_URL}/packages/{package['PackageBase']}",
            "source": srcinfo["source"],
        }
        # recipes for computing source checksums according to its type (bzr, hg,
        # git or file) can be found in the pacman repository:
        # https://gitlab.archlinux.org/pacman/pacman/-/tree/master/scripts/libmakepkg/source
        for checksums in ("sha256sums", "sha512sums", "b2sums", "md5sums"):
            if checksums in srcinfo:
                package_srcinfo[checksums] = srcinfo[checksums]
        print(json.dumps(package_srcinfo))


if __name__ == "__main__":
    run()
