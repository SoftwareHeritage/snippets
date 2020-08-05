import bz2
import contextlib
import datetime
import gzip
import hashlib
import io
import lzma
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
from typing import Optional
from unittest.mock import patch

import click
import msgpack

from swh.core.api.classes import stream_results
from swh.loader.package.archive.loader import ArchivePackageInfo, ArchiveLoader
from swh.model.hashutil import hash_to_bytes, hash_to_hex, MultiHash
from swh.model.identifiers import SWHID
from swh.model.model import (
    Content,
    MetadataAuthority,
    MetadataAuthorityType,
    MetadataFetcher,
    MetadataTargetType,
    Sha1Git,
    RawExtrinsicMetadata,
)
from swh.storage import get_storage
from swh.storage.algos.snapshot import snapshot_get_all_branches
from swh.storage.interface import StorageInterface
from swh.vault.to_disk import DirectoryBuilder


AUTHORITY = MetadataAuthority(
    type=MetadataAuthorityType.FORGE, url="http://localhost/", metadata={},
)

FETCHER = MetadataFetcher(
    name="tarball-metadata-archiver", version="0.0.0", metadata={}
)


@contextlib.contextmanager
def mock_config():
    with tempfile.NamedTemporaryFile(suffix=".yml") as fd:
        fd.write(b"storage: {cls: memory}\n")
        fd.flush()
        # fd.seek(0)

        with patch.dict(os.environ, {"SWH_CONFIG_FILENAME": fd.name}):
            yield


class LocalArchiveLoader(ArchiveLoader):
    def download_package(self, p_info: ArchivePackageInfo, tmpdir: str):
        return [(p_info.url, {})]


def revision_swhid_from_status(storage, status):
    assert status["snapshot_id"] is not None
    snapshot_id = hash_to_bytes(status["snapshot_id"])

    snapshot_branches = snapshot_get_all_branches(storage, snapshot_id)["branches"]
    assert snapshot_branches is not None
    for (branch_name, branch) in snapshot_branches.items():
        if branch["target_type"] == "revision":
            revision_id = branch["target"]
            break
    else:
        assert False, "no branch"

    assert list(storage.revision_missing([revision_id])) == []
    return SWHID(object_type="revision", object_id=hash_to_hex(revision_id))


def ingest_tarball(
    storage: StorageInterface, source_path: str, *, verbose: bool
) -> Sha1Git:
    """Ingests a tarball in the storage, returns the revision's SWHID"""
    url = "file://" + os.path.abspath(source_path)
    with mock_config():
        loader = LocalArchiveLoader(
            url=url,
            artifacts=[
                {
                    "time": "2020-01-01",
                    "url": source_path,
                    "length": os.stat(source_path).st_size,
                    "version": "0.0.0",
                }
            ],
        )

    loader.storage = storage

    status = loader.load()
    if status["status"] != "eventful":
        return None

    revision_swhid = revision_swhid_from_status(storage, status)

    storage.metadata_authority_add([AUTHORITY])
    storage.metadata_fetcher_add([FETCHER])

    if source_path.endswith((".tar.gz", ".tar.bz2", ".tar.xz", ".tgz", ".tbz2")):
        type_ = "tar"
    elif source_path.endswith((".zip",)):
        type_ = "zip"

    with tempfile.NamedTemporaryFile() as delta_fd:
        proc = subprocess.run(
            ["pristine-" + type_, "gendelta", source_path, delta_fd.name],
            capture_output=True,
        )
        assert proc.returncode == 0, proc
        pristine_delta = delta_fd.read()
    if verbose:
        print(f"Size of pristine delta: {len(pristine_delta)} bytes")

    pristine = {b"type": type_, b"delta": pristine_delta}

    tar_metadata = {
        b"filename": os.path.basename(source_path),
        b"pristine": pristine,
    }

    storage.raw_extrinsic_metadata_add(
        [
            RawExtrinsicMetadata(
                type=MetadataTargetType.REVISION,
                id=revision_swhid,
                discovery_date=datetime.datetime.now(),
                authority=AUTHORITY,
                fetcher=FETCHER,
                format="tarball-metadata-msgpack",
                metadata=msgpack.dumps(tar_metadata),
            )
        ]
    )

    return revision_swhid


def get_tar_metadata(
    storage: StorageInterface, revision_swhid: SWHID,
):
    """Return the stored metadata for the given revision."""
    metadata = stream_results(
        storage.raw_extrinsic_metadata_get,
        type=MetadataTargetType.REVISION,
        id=revision_swhid,
        authority=AUTHORITY,
    )
    last_metadata = None
    for item in metadata:
        if item.fetcher.name == FETCHER.name:
            last_metadata = item
    assert last_metadata is not None

    assert last_metadata.format == "tarball-metadata-msgpack"

    return msgpack.loads(last_metadata.metadata)


def generate_tarball(
    storage: StorageInterface,
    revision_swhid: SWHID,
    target_path: str,
    *,
    verbose: bool,
):
    """Using only the storage and revision SWHID, regenerates a tarball
    identical to the source tarball."""
    tar_metadata = get_tar_metadata(storage, revision_swhid)

    revision_id = hash_to_bytes(revision_swhid.object_id)
    revision = list(storage.revision_get([revision_id]))[0]

    with tempfile.TemporaryDirectory() as tempdir:
        dir_builder = DirectoryBuilder(storage, tempdir.encode(), revision["directory"])
        dir_builder.build()

        type_ = tar_metadata[b"pristine"][b"type"].decode()
        assert type_ in ("tar", "zip"), f"Unknown type {type_}"

        # pristine-tar needs a different CWD depending on the number of root
        # directory of the tarball
        root_dirs = os.listdir(tempdir)
        if type_ == "tar" and len(root_dirs) == 1:
            cwd = os.path.join(tempdir, root_dirs[0])
        else:
            cwd = tempdir

        with tempfile.NamedTemporaryFile() as delta_fd:
            delta_fd.write(tar_metadata[b"pristine"][b"delta"])
            delta_fd.flush()

            proc = subprocess.run(
                ["pristine-" + type_, "gen" + type_, delta_fd.name, target_path],
                cwd=cwd,
                capture_output=True,
            )

    if proc.returncode != 0:
        print(proc.stdout.decode())
        print(proc.stderr.decode())
    return proc.returncode == 0


def check_files_equal(source_path, target_path):
    with open(source_path, "rb") as source_fd, open(target_path, "rb") as target_fd:
        while True:
            source_chunk = source_fd.read(512)
            target_chunk = target_fd.read(512)
            if source_chunk != target_chunk:
                return False
            if not source_chunk:
                return True


def run_one(source_path: str, target_path: Optional[str] = None, *, verbose: bool):
    storage = get_storage("memory")

    if verbose:
        print(f"{source_path}: ingesting")

    revision_swhid = ingest_tarball(storage, source_path, verbose=verbose)
    if revision_swhid is None:
        print(f"{source_path} could not be loaded")
        return (True, None)

    if verbose:
        print(f"{source_path}: reproducing")
    tar_metadata = get_tar_metadata(storage, revision_swhid)
    original_filename = tar_metadata[b"filename"]

    if target_path is None:
        target_file = tempfile.NamedTemporaryFile(suffix=original_filename)
        target_path = target_file.name
    else:
        target_file = None

    success = generate_tarball(storage, revision_swhid, target_path, verbose=verbose)

    if not success:
        print(f"{source_path} could not be generated")
        reproducible = False
    elif check_files_equal(source_path, target_path):
        print(f"{source_path} is reproducible")
        reproducible = True
    else:
        print(f"{source_path} is not reproducible")
        reproducible = False

    return (reproducible, target_file)


@click.group()
def cli():
    pass


@cli.command()
@click.option(
    "--diffoscope", default=False, is_flag=True, help="Run diffoscope before exiting."
)
@click.option("--verbose", is_flag=True, help="Verbose mode")
@click.argument("source_path")
@click.argument("target_path", default="")
def single(diffoscope, source_path, target_path, verbose):
    target_file = run_one(source_path, target_path or None, verbose=verbose)

    if diffoscope:
        if not target_path:
            target_path = target_file.name

        proc = subprocess.run(["diffoscope", source_path, target_path])
        exit(proc.returncode)


@cli.command()
@click.argument("source_path")
@click.argument("target_dir")
def checkout(source_path, target_dir):
    """Loads the source_path into the storage, then extracts it into the target_dir."""
    storage = get_storage("memory")
    revision_swhid = ingest_tarball(storage, source_path, verbose=False)
    revision_id = hash_to_bytes(revision_swhid.object_id)
    revision = list(storage.revision_get([revision_id]))[0]

    tar_metadata = get_tar_metadata(storage, revision_swhid)
    original_filename = tar_metadata[b"filename"]

    target_file = tempfile.NamedTemporaryFile(suffix=original_filename)
    target_path = target_file.name

    dir_builder = DirectoryBuilder(storage, target_dir.encode(), revision["directory"])
    dir_builder.build()


@cli.command()
@click.argument("source_paths", nargs=-1)
@click.option("--verbose", is_flag=True, help="Verbose mode")
@click.option(
    "--fail-early", is_flag=True, help="Stop after the first unreproducible tarball"
)
def many(source_paths, verbose, fail_early):
    success = True

    for source_path in source_paths:
        (reproducible, _) = run_one(source_path, verbose=verbose)
        success = success and reproducible
        if fail_early and not reproducible:
            break

    exit(0 if success else 1)


if __name__ == "__main__":
    exit(cli())
