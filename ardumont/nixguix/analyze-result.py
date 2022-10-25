# Copyright (C) 2022 the Software Heritage developers
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information

import re
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable
from urllib.parse import urlparse

import click

DATASET_DIR = "/var/tmp/nixguix/dataset"


PATTERN_ONLY_VERSION = re.compile(r"(v*[0-9]+[.])([0-9]+[.]*)+")

PATTERN_ENDING_VERSION = re.compile(r"(.*)([0-9]+[\.]*)+$")


def read_dataset(filepath: str) -> Iterable[str]:
    """Read the dataset file."""
    with open(filepath, "r") as f:
        for line in f:
            yield line.rstrip()


def group_by_extensions(data: Iterable[str]) -> Dict[str, int]:
    """Group the data read by extensions."""
    extensions: Dict[str, int] = defaultdict(int)
    for url in data:
        urlparsed = urlparse(url)
        suffixes = Path(urlparsed.path).suffixes
        if suffixes:
            if ".patch" in suffixes or ".patch" in suffixes[-1]:
                key = ".patch"
            elif ".git" in suffixes or ".git" in suffixes[-1]:
                key = ".git"
            elif ".cgi" in suffixes or ".cgi" in suffixes[-1]:
                key = ".cgi"
            else:
                name = Path(urlparsed.path).name
                if PATTERN_ONLY_VERSION.match(name):
                    key = "only-version-should-be-tarball"
                elif PATTERN_ENDING_VERSION.match(name):
                    key = "ending-version-ok"
                else:
                    key = suffixes[-1]
            extensions[key] += 1
    return dict(extensions)


@click.command()
@click.option("--dataset-date", help="The date of the extracted dataset e.g. 20221025")
@click.option(
    "--dataset", "datasets", multiple=True, type=click.Choice(["guix", "nixpkgs"])
)
@click.option("--obj-type", type=click.Choice(["contents", "directories"]))
def main(dataset_date, datasets, obj_type):
    """For each dataset required, read and group by extensions the dataset."""
    for dataset_name in datasets:
        filepath = f"{DATASET_DIR}/{dataset_date}/list-{obj_type}-{dataset_name}.csv"
        data = read_dataset(filepath)
        print(f"dataset <{dataset_name}> with type {obj_type}: {filepath}\n")
        extensions = group_by_extensions(data)
        from pprint import pprint

        pprint(extensions)
        print()


if __name__ == "__main__":
    main()
