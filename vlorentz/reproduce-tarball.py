import bz2
import contextlib
import datetime
import glob
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
    TargetType,
)
from swh.storage import get_storage
from swh.storage.algos.snapshot import snapshot_get_all_branches
from swh.storage.interface import StorageInterface
from swh.vault.to_disk import DirectoryBuilder


AUTHORITY = MetadataAuthority(
    type=MetadataAuthorityType.FORGE,
    url="http://localhost/",
    metadata={},
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
    def get_loader_version(self):
        return "0.0.0"

    def download_package(self, p_info: ArchivePackageInfo, tmpdir: str):
        return [(p_info.url, {})]


def revision_swhid_from_status(storage, status):
    assert status["snapshot_id"] is not None
    snapshot_id = hash_to_bytes(status["snapshot_id"])

    snapshot_branches = snapshot_get_all_branches(storage, snapshot_id).branches
    assert snapshot_branches is not None
    for (branch_name, branch) in snapshot_branches.items():
        if branch.target_type == TargetType.REVISION:
            revision_id = branch.target
            break
    else:
        assert False, "no branch"

    assert list(storage.revision_missing([revision_id])) == []
    return SWHID(object_type="revision", object_id=hash_to_hex(revision_id))


def pristine_gendelta(source_path):
    if source_path.endswith((".tar.gz", ".tar.bz2", ".tar.xz", ".tgz", ".tbz2")):
        type_ = "tar"
        extra_options = []
    elif source_path.endswith((".zip",)):
        type_ = "zip"
        extra_options = ["--lax-guess"]
    else:
        assert False, source_path

    with tempfile.NamedTemporaryFile() as delta_fd:
        proc = subprocess.run(
            [
                "pristine-" + type_,
                *extra_options,
                "gendelta",
                source_path,
                delta_fd.name,
            ],
            capture_output=True,
        )
        assert proc.returncode == 0, proc
        pristine_delta = delta_fd.read()
        overhead_size = len(pristine_delta)

    pristine = {b"type": type_, b"delta": pristine_delta}

    tar_metadata = {
        b"filename": os.path.basename(source_path),
        b"pristine": pristine,
    }

    return (tar_metadata, overhead_size)


def disarchive_save(source_path):
    with tempfile.TemporaryDirectory(suffix="_src_dirdb") as dirdb:
        proc = subprocess.run(["sha256sum", source_path], capture_output=True)
        assert proc.returncode == 0
        source_sha256 = proc.stdout.decode().strip().split()[0]
        with tempfile.TemporaryDirectory(suffix="src_dircache") as dircache:
            proc = subprocess.run(
                ["disarchive", "save", source_path],
                env={
                    **os.environ,
                    "DISARCHIVE_DB": dirdb,
                    "DISARCHIVE_DIRCACHE": dircache,
                },
                capture_output=True,
            )
            dircache_dirs = os.listdir(os.path.join(dircache, "sha256"))
            (dircache_sha256,) = dircache_dirs
        assert proc.returncode == 0, proc
        with tempfile.NamedTemporaryFile(suffix=".tar.gz") as disarchive_db_fd:
            proc = subprocess.run(
                ["tar", "-cz", ".", "-f", disarchive_db_fd.name],
                cwd=dirdb,
                capture_output=True,
            )
            assert proc.returncode == 0, proc
            disarchive_db = disarchive_db_fd.read()
        overhead_size = len(disarchive_db)

    tar_metadata = {
        b"filename": os.path.basename(source_path),
        b"sha256": source_sha256,
        b"disarchive": {b"dircache_sha256": dircache_sha256, b"disarchive_db": disarchive_db},
    }

    return (tar_metadata, overhead_size)


def ingest_tarball(
    method, storage: StorageInterface, source_path: str, *, verbose: bool
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
        return (None, None)

    revision_swhid = revision_swhid_from_status(storage, status)

    storage.metadata_authority_add([AUTHORITY])
    storage.metadata_fetcher_add([FETCHER])

    if method == "pristine":
        (tar_metadata, overhead_size) = pristine_gendelta(source_path)
    else:
        (tar_metadata, overhead_size) = disarchive_save(source_path)

    if verbose:
        print(f"Tarball overhead: {overhead_size} bytes")

    storage.raw_extrinsic_metadata_add(
        [
            RawExtrinsicMetadata(
                type=MetadataTargetType.REVISION,
                id=revision_swhid,
                discovery_date=datetime.datetime.now(tz=datetime.timezone.utc),
                authority=AUTHORITY,
                fetcher=FETCHER,
                format=f"tarball-metadata-msgpack-{method}",
                metadata=msgpack.dumps(tar_metadata),
            )
        ]
    )

    return (revision_swhid, overhead_size)


def get_tar_metadata(
    method: str,
    storage: StorageInterface,
    revision_swhid: SWHID,
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

    assert last_metadata.format == f"tarball-metadata-msgpack-{method}"

    return msgpack.loads(last_metadata.metadata)


def generate_tarball_pristine(
    storage: StorageInterface,
    revision_swhid: SWHID,
    target_path: str,
    *,
    verbose: bool,
):
    """Using only the storage and revision SWHID, regenerates a tarball
    identical to the source tarball."""
    tar_metadata = get_tar_metadata("pristine", storage, revision_swhid)

    revision_id = hash_to_bytes(revision_swhid.object_id)
    revision = list(storage.revision_get([revision_id]))[0]

    with tempfile.TemporaryDirectory() as tempdir:
        dir_builder = DirectoryBuilder(storage, tempdir.encode(), revision["directory"])
        dir_builder.build()

        type_ = tar_metadata[b"pristine"][b"type"]
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


def generate_tarball_disarchive(
    storage: StorageInterface,
    revision_swhid: SWHID,
    target_path: str,
    *,
    verbose: bool,
):
    """Using only the storage and revision SWHID, regenerates a tarball
    identical to the source tarball."""
    tar_metadata = get_tar_metadata("disarchive", storage, revision_swhid)

    revision_id = hash_to_bytes(revision_swhid.object_id)
    revision = list(storage.revision_get([revision_id]))[0]

    source_sha256 = tar_metadata[b"sha256"]
    dircache_sha256 = tar_metadata[b"disarchive"][b"dircache_sha256"]

    with tempfile.TemporaryDirectory(suffix="_dest_dircache") as dircache:
        checkout_dir = dircache + "/sha256/" + dircache_sha256
        dir_builder = DirectoryBuilder(
            storage,
            checkout_dir.encode(),
            revision["directory"],
        )
        dir_builder.build()

        assert os.path.isdir(checkout_dir)

        with tempfile.TemporaryDirectory(suffix="_dest_dirdb") as dirdb:
            with tempfile.NamedTemporaryFile(suffix=".tar.gz") as dirdb_fd:
                dirdb_fd.write(tar_metadata[b"disarchive"][b"disarchive_db"])
                dirdb_fd.flush()
                proc = subprocess.run(
                    ["tar", "-xf", dirdb_fd.name],
                    cwd=dirdb,
                    capture_output=True,
                )
                assert proc.returncode == 0, proc

            proc = subprocess.run(
                ["disarchive", "load", source_sha256, target_path],
                env={
                    **os.environ,
                    "DISARCHIVE_DB": dirdb,
                    "DISARCHIVE_DIRCACHE": dircache,
                },
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


def run_one(
    method: str, source_path: str, target_path: Optional[str] = None, *, verbose: bool
):
    storage = get_storage("memory")

    if not os.path.isfile(source_path):
        print(f"{source_path}: skipping, not a file")
        return (True, None)

    proc = subprocess.run(["file", source_path], capture_output=True)
    proc.check_returncode()
    if b"ASCII text" in proc.stdout or b"Unicode text" in proc.stdout:
        print(f"{source_path}: skipping, not an archive file")
        return (True, None)

    if verbose:
        print(f"{source_path}: ingesting")

    (revision_swhid, delta_size) = ingest_tarball(
        method, storage, source_path, verbose=verbose
    )
    if revision_swhid is None:
        print(f"{source_path} could not be loaded")
        return (True, None)

    if verbose:
        print(f"{source_path}: reproducing")
    tar_metadata = get_tar_metadata(method, storage, revision_swhid)
    original_filename = tar_metadata[b"filename"]

    if target_path is None:
        target_file = tempfile.NamedTemporaryFile(suffix=original_filename)
        target_path = target_file.name
    else:
        target_file = None

    if method == "pristine":
        success = generate_tarball_pristine(
            storage, revision_swhid, target_path, verbose=verbose
        )
    else:
        assert method == "disarchive"
        success = generate_tarball_disarchive(
            storage, revision_swhid, target_path, verbose=verbose
        )

    if not success:
        print(f"{source_path} could not be generated")
        reproducible = False
    elif check_files_equal(source_path, target_path):
        source_size = os.stat(source_path).st_size
        print(
            f"{source_path} is reproducible (delta is {delta_size} bytes, {int(100*delta_size/source_size)}% of the original file)"
        )
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
@click.option(
    "--method", type=click.Choice(["pristine", "disarchive"]), default="pristine"
)
@click.argument("source_path")
@click.argument("target_path", default="")
def single(diffoscope, source_path, target_path, verbose, method):
    target_file = run_one(method, source_path, target_path or None, verbose=verbose)

    if diffoscope:
        if not target_path:
            target_path = target_file.name

        proc = subprocess.run(["diffoscope", source_path, target_path])
        exit(proc.returncode)


@cli.command()
@click.option(
    "--method", type=click.Choice(["pristine", "disarchive"]), default="pristine"
)
@click.argument("source_path")
@click.argument("target_dir")
def checkout(source_path, target_dir, method):
    """Loads the source_path into the storage, then extracts it into the target_dir."""
    storage = get_storage("memory")
    (revision_swhid, _) = ingest_tarball(method, storage, source_path, verbose=False)
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
    "--method", type=click.Choice(["pristine", "disarchive"]), default="pristine"
)
@click.option(
    "--fail-early", is_flag=True, help="Stop after the first unreproducible tarball"
)
@click.option(
    "--pattern",
    is_flag=True,
    help=(
        "Interpret the source paths as patterns (ie. *, **, and ?). "
        "This is useful when the list of files is too long for the interpreter)"
    ),
)
def many(source_paths, verbose, method, fail_early, pattern):
    if pattern:
        patterns = source_paths
        source_paths = []
        for pattern in patterns:
            source_paths.extend(glob.glob(pattern, recursive=True))

    for source_path in source_paths:
        (reproducible, _) = run_one(method, source_path, verbose=verbose)
        success = success and reproducible
        if fail_early and not reproducible:
            break

    exit(0 if success else 1)


if __name__ == "__main__":
    exit(cli())
