#!/usr/bin/env python3

# Copyright (C) 2024  The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information

# Simple script to identify bogus extids associated to hg-checkout visits
# as associated loader was archiving .hg folders after first deployment

import string

import requests

GUIX_SOURCES_JSON_URL = "https://guix.gnu.org/sources.json"

SWH_API_BASE_URL = "https://archive.softwareheritage.org/api/1"

SWH_API_EXTID_ENDPOINT_URL_TEMPLATE = string.Template(
    f"{SWH_API_BASE_URL}/extid/$extid_type/base64url:$extid/?extid_version=1"
)

SWH_API_DIRECTORY_ENDPOINT_URL_TEMPLATE = string.Template(
    f"{SWH_API_BASE_URL}/directory/$dir_id/"
)


def base64_url_hash(base_64_hash):
    return base_64_hash.replace("+", "-").replace("/", "_").rstrip("=")


guix_sources = requests.get(GUIX_SOURCES_JSON_URL).json()

extids_to_remove = []

for source in guix_sources["sources"]:
    if source["type"] != "hg":
        # not a mercurial source
        continue

    algo, nar_hash = source["integrity"].split("-", maxsplit=1)

    extid_url = SWH_API_EXTID_ENDPOINT_URL_TEMPLATE.substitute(
        extid_type=f"nar-{algo}", extid=base64_url_hash(nar_hash)
    )

    extid_data = requests.get(extid_url).json()

    if extid_data.get("exception") == "NotFoundExc":
        continue

    _, _, _, target_dir = extid_data["target"].split(":")

    dir_url = SWH_API_DIRECTORY_ENDPOINT_URL_TEMPLATE.substitute(dir_id=target_dir)

    dir_data = requests.get(dir_url).json()

    if ".hg" in [entry["name"] for entry in dir_data if entry["type"] == "dir"]:
        # target directory contains a .hg sub-directory, extid must be removed
        extids_to_remove.append(nar_hash)

print("\n".join(extids_to_remove))
