#!/usr/bin/env python3

"""list all SourceForge projects using sitemap(s)

Example:

    $ sourceforge-ls-projects.py | sort > sourceforge-projects.txt

"""

__copyright__ = "Copyright (C) 2020  Stefano Zacchiroli"
__license__ = "GPL-3.0-or-later"


import logging
import re
import requests
import xml.etree.ElementTree as ET

from pathlib import Path


SITEMAP_INDEX_URL = "https://sourceforge.net/allura_sitemap/sitemap.xml"
PROJ_URL_RE = re.compile("^https://sourceforge.net/([^/]+)/([^/]+)/(.*)")
CACHE_DIR = Path("~/.cache/swh/sourceforge-lister").expanduser()


def download(url, use_cache=True):
    """URL downloader backed by on-disk cache

    """
    cache_name = CACHE_DIR / url.split("/")[-1]

    if not use_cache or not cache_name.exists():
        logging.info(f"downloading {url} ...")
        r = requests.get(url)
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        with open(cache_name, "w") as f:
            f.write(r.text)

    with open(cache_name) as f:
        return f.read()


def ls_projects(sitemap_url):
    """(download and) parse sitemaps to extract project URLs

    """
    idx = ET.fromstring(download(SITEMAP_INDEX_URL))

    for map_loc in idx.findall(".//{*}sitemap/{*}loc"):
        map_url = map_loc.text
        sub_idx = ET.fromstring(download(map_url))

        known_projs = set()  # hash()-es of known projects
        for proj in sub_idx.findall(".//{*}url"):
            proj_url = proj.find("{*}loc").text
            if m := PROJ_URL_RE.match(proj_url):
                namespace = m.group(1)
                if namespace == "projects":
                    # These have a `/p/` counterparts
                    continue
                proj_name = m.group(2)  # base project url
                rest = m.group(3)
                if rest.count("/") > 1:
                    # This is a subproject
                    proj_name = f"{proj_name}/{rest.rsplit('/', 2)[0]}"

                h = hash(proj_name)
                if h not in known_projs:
                    known_projs.add(h)
                    yield f"{namespace}/{proj_name}"


def main():
    logging.basicConfig(level=logging.INFO)
    for proj_name in ls_projects(SITEMAP_INDEX_URL):
        print(proj_name)


if __name__ == "__main__":
    main()
