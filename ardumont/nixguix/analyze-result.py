# Copyright (C) 2022 the Software Heritage developers
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information

from collections import defaultdict
from pathlib import Path
from typing import Dict, List

import click

DATASET_DIR = "/var/tmp/nixguix/dataset"


def read_dataset(date_dir: str, obj_type: str, dataset_name: str) -> List[str]:
    """Read the dataset file."""
    filepath = f"{DATASET_DIR}/{date_dir}/list-contents-{dataset_name}.csv"
    with open(filepath, "r") as f:
        data = [line.rstrip() for line in f]
    return data


def group_by_extensions(data: List[str]) -> Dict[str, int]:
    """Group the data read by extensions."""
    extensions: Dict[str, int] = defaultdict(int)
    for url in data:
        suffixes = Path(url).suffixes
        if suffixes:
            if ".patch" in suffixes or ".patch" in suffixes[-1]:
                key = ".patch"
            elif ".git" in suffixes or ".git" in suffixes[-1]:
                key = ".git"
            elif ".cgi" in suffixes or ".cgi" in suffixes[-1]:
                key = ".cgi"
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
        data = read_dataset(dataset_date, obj_type, dataset_name)
        print(f"dataset: {dataset_name}\n")
        extensions = group_by_extensions(data)
        from pprint import pprint

        pprint(extensions)
        print()


if __name__ == "__main__":
    main()
