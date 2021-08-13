# Copyright (C) 2021  The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information

import contextlib
import datetime
import io
import os.path
import pathlib
import subprocess
import sys
import tempfile
from typing import Dict, Set

import yaml

from swh.loader.git.from_disk import GitLoaderFromDisk
from swh.model.hashutil import hash_to_bytes, hash_to_hex
from swh.model.identifiers import CoreSWHID
from swh.model.model import Sha1Git
from swh.storage import get_storage

CONFIG_PATH = pathlib.Path("vault-local.yml")


def list_object_ids(path: pathlib.Path) -> Set[Sha1Git]:
    """Returns the set of all object hashes in the given repo path."""
    print(f"Reading {path}...")
    stdout1 = subprocess.check_output(
        ["git", "rev-list", "--objects", "--all"], cwd=path
    )
    stdout2 = subprocess.check_output(
        ["git", "rev-list", "--objects", "-g", "--no-walk", "--all"], cwd=path,
    )
    obj_ids = [
        line.split()[0].decode("ascii")
        for line in (stdout1 + stdout2).split(b"\n")
        if line
    ]
    return set(map(hash_to_bytes, obj_ids))


def list_refs(path: pathlib.Path) -> Dict[bytes, bytes]:
    packed_refs_path = path / "packed-refs"
    if packed_refs_path.is_file():
        refs = {
            ref_name: target
            for (target, ref_name) in [
                line.split()
                for line in open(packed_refs_path)
                if (
                    line
                    and not line.startswith("#")  # header
                    and not line.startswith("^")  # wat?
                )
            ]
        }
    else:
        refs = {}

    # refs/ takes precedence over packed-refs (although it's unlikely they would
    # ever disagree on a target)
    refs.update(
        {
            str(ref_name.relative_to(path)): open(ref_name).read()
            for ref_name in path.glob("refs/**/*")
            if ref_name.is_file()
        }
    )

    return refs


def load_repo(path: pathlib.Path, storage_config) -> CoreSWHID:
    """Loads a repo to the storage and returns its snapshot id"""
    print(f"Loading {path}...")
    storage = get_storage(
        "pipeline",
        steps=[
            dict(cls="validate"),
            dict(
                cls="buffer",
                min_batch_size=dict(
                    content=10000,
                    content_bytes=104857600,
                    directory=1000,
                    revision=1000,
                ),
            ),
            dict(cls="filter"),
            storage_config,
        ],
    )

    loader = GitLoaderFromDisk(
        storage,
        f"file://{path.resolve()}",
        directory=str(path),
        visit_date=datetime.datetime.now(datetime.timezone.utc),
    )

    loader.load()

    return loader.snapshot.swhid()


def cook_repo(config_path, storage, swhid: CoreSWHID, path: pathlib.Path) -> None:
    """Reads the storage to cook the swhid to the given path"""
    print(f"Cooking {swhid} to {path}...")
    with tempfile.NamedTemporaryFile(prefix="vault-repro-", suffix=".tar") as tar_fd:
        tar_path = tar_fd.name
        subprocess.run(
            [
                "swh",
                "vault",
                "cook",
                "-C",
                str(config_path),
                str(swhid),
                str(tar_path),
                "--cooker-type",
                "git_bare",
            ],
            check=True,
        )

        subprocess.run(["tar", "-xf", tar_path], cwd=path, check=True)


def repro_repo(config_path, path: pathlib.Path) -> None:
    with open(config_path) as fd:
        vault_config = yaml.safe_load(fd)

    storage = get_storage(**vault_config["storage"])

    swhid = load_repo(path, vault_config["storage"])

    with tempfile.TemporaryDirectory(prefix="vault-repro-") as cooked_output_path_str:
        cooked_output_path = pathlib.Path(cooked_output_path_str)
        cook_repo(config_path, storage, swhid, cooked_output_path)
        cooked_ids = list_object_ids(cooked_output_path / f"{swhid}.git")
        cooked_refs = list_refs(cooked_output_path / f"{swhid}.git")

    original_ids = list_object_ids(path)

    missing_ids = original_ids - cooked_ids
    extra_ids = cooked_ids - original_ids

    print(f"{len(original_ids)} original objects, {len(cooked_ids)} cooked objects.")
    if missing_ids:
        print("Missing objects:", " ".join(map(hash_to_hex, sorted(missing_ids))))
    if extra_ids:
        print("Extra objects:", " ".join(map(hash_to_hex, sorted(extra_ids))))
    if missing_ids or extra_ids:
        exit(1)

    original_refs = list_refs(path)

    missing_refs = set(original_refs) - set(cooked_refs)
    extra_refs = set(cooked_refs) - set(original_refs)
    if missing_refs:
        print("Missing refs:", " ".join(map(str, missing_refs)))
    if extra_refs:
        print("Extra refs:", " ".join(map(str, missing_refs)))
    mismatched_refs = False
    for ref_name in original_refs:
        if original_refs[ref_name] != cooked_refs[ref_name]:
            mismatched_refs = True
            print(
                "Mismatched ref:",
                ref_name,
                "points to",
                cooked_refs[ref_name],
                "instead of",
                original_refs[ref_name],
            )

    if missing_refs or extra_refs or missing_refs:
        exit(1)

    print("All good!")


@contextlib.contextmanager
def clone_repo(repo_path_or_url):
    if os.path.isdir(repo_path_or_url):
        # nothing to do, it's already cloned
        yield repo_path_or_url
    else:
        with tempfile.TemporaryDirectory(
            prefix="vault-repro-", suffix=".git"
        ) as cloned_path:
            os.rmdir(cloned_path)
            subprocess.run(
                ["git", "--bare", "clone", repo_path_or_url, cloned_path], check=True,
            )
            yield cloned_path


def main() -> None:
    (_, config_path, repo_path_or_url) = sys.argv

    with clone_repo(repo_path_or_url) as repo_path:
        repro_repo(config_path, pathlib.Path(repo_path))


if __name__ == "__main__":
    main()
