#!/usr/bin/env python3

# Copyright (C) 2023  The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information

# Generate a list of origin URLs expected by the CVS loader for SWH by
# crawling CVS module names from CVS repositories hosted on Sourceware

import os
import subprocess

import requests

cvs_origin_urls = []

for cvs_origin in open("sourceware_cvs_origins", "r"):
    cvs_origin = cvs_origin.rstrip("\n")
    rsync_ls = subprocess.check_output(["rsync", cvs_origin + "/"]).decode()
    cvs_modules = []
    for line in rsync_ls.split("\n"):
        if not line:
            continue
        _, _, _, _, cvs_module = line.split()
        cvs_modules.append(cvs_module)
    if "CVSROOT" not in cvs_modules:
        continue
    for cvs_module in cvs_modules:
        if cvs_module not in (
            ".",
            "CVS",
            "CVSROOT",
            "Attic",
        ) and not cvs_module.endswith(",v"):
            cvs_origin_url = cvs_origin + "/" + cvs_module
            cvs_origin_urls.append(cvs_origin_url)

SWH_API_BASE_URL = "https://archive.softwareheritage.org/api/1"

headers = {}
if "SWH_TOKEN" in os.environ:
    headers["Authorization"] = f"Bearer {os.environ['SWH_TOKEN']}"

for cvs_origin_url in cvs_origin_urls:
    requests.post(
        f"{SWH_API_BASE_URL}/origin/save/cvs/url/{cvs_origin_url}/", headers=headers
    )
