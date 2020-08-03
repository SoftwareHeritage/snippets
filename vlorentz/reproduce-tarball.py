import contextlib
import datetime
import hashlib
import io
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


AUTHORITY = MetadataAuthority(
    type=MetadataAuthorityType.FORGE, url="http://localhost/", metadata={},
)

FETCHER = MetadataFetcher(
    name="tarball-metadata-archiver", version="0.0.0", metadata={}
)


class BufPreservingTarInfo(tarfile.TarInfo):
    r"""Makes tobuf return a value bit-for-bit identical to the one passed to
    frombuf.

    This avoids a round-trip of decoding then re-encoding, which is lossy as
    decoding is not injective (eg. b"\x00" and b"00000\x00" are both decoded
    as 0 for null-terminated ASCII numbers).
    """
    buf: bytes

    @classmethod
    def frombuf(cls, buf, encoding, errors):
        tar_info = super().frombuf(buf, encoding, errors)
        tar_info.buf = buf
        return tar_info

    def tobuf(self, *args, **kwargs):
        return self.buf


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


def magic_number_to_format(magic_number):
    if magic_number == tarfile.GNU_MAGIC:
        return tarfile.GNU_FORMAT
    elif magic_number == tarfile.POSIX_MAGIC:
        return tarfile.PAX_FORMAT
    else:
        raise ValueError("Unknown magic number %r" % magic_number)


def ingest_tarball(storage: StorageInterface, source_path: str) -> Sha1Git:
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
    assert status["status"] == "eventful"
    assert status["snapshot_id"] is not None
    snapshot_id = hash_to_bytes(status["snapshot_id"])

    snapshot_branches = snapshot_get_all_branches(storage, snapshot_id)
    assert snapshot_branches is not None
    for (branch_name, branch_target) in snapshot_branches.items():
        revision_id = branch_target
        break
    else:
        assert False, "no branch"
    revision_swhid = SWHID(object_type="revision", object_id=hash_to_hex(revision_id))

    storage.metadata_authority_add([AUTHORITY])
    storage.metadata_fetcher_add([FETCHER])

    """
    with open(source_path, "rb") as fd:
        first_chunk = fd.read(512)
        magic_number = first_chunk[257:265]
    """
    with tarfile.open(source_path, tarinfo=BufPreservingTarInfo,) as tf:
        magic_number = tf.firstmember.buf[257:265]

    format = magic_number_to_format(magic_number)

    with tarfile.open(
        source_path,
        encoding="utf-8",
        errors="strict",
        tarinfo=BufPreservingTarInfo,
        format=format,
    ) as tf:
        members_metadata = []
        for member in tf.getmembers():
            with tempfile.NamedTemporaryFile() as member_fd:
                # FIXME: we can spare the disk write by rewriting makefile
                tf.makefile(member, member_fd.name)

                content = Content.from_data(member_fd.read())

            # TODO: if 'member' is sparse, dig matching holes in the content.
            # (currently, this would produce a corrupted tarball)

            assert member.size == content.length

            if member.isfile():
                # should have been added by the storage
                assert not list(storage.content_missing([content.hashes()])), (
                    member,
                    content,
                )

            members_metadata.append(
                {"header": member.buf, "hashes": content.hashes(),}
            )

        (_, ext) = os.path.splitext(source_path)
        ext = ext[1:]
        if ext == "tar":
            pristine = None
        else:
            assert ext in ("gz", "bz2", "xz"), ext
            proc = subprocess.run(
                ["pristine-" + ext, "gendelta", source_path, "-"], capture_output=True
            )
            assert proc.returncode == 0, proc
            pristine = {b"type": ext.encode(), b"delta": proc.stdout}

        tar_metadata = {
            b"filename": os.path.basename(source_path),
            b"pristine": pristine,
            b"global": {
                b"magic_number": magic_number,
                b"encoding": tf.encoding,
                b"pax_headers": tf.pax_headers,
            },
            b"members": members_metadata,
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
    storage: StorageInterface, revision_swhid: SWHID, target_path: str
):
    tar_metadata = get_tar_metadata(storage, revision_swhid)

    global_metadata = tar_metadata[b"global"]
    format = magic_number_to_format(global_metadata[b"magic_number"])

    with tarfile.TarFile(
        target_path,
        "w",
        format=format,
        pax_headers={
            k.decode(): v.decode() for (k, v) in global_metadata[b"pax_headers"].items()
        },
        encoding=global_metadata[b"encoding"].decode(),
        errors="strict",
    ) as tf:
        for member_metadata in tar_metadata[b"members"]:
            contents = list(storage.content_get([member_metadata[b"hashes"][b"sha1"]]))
            tar_info = BufPreservingTarInfo.frombuf(
                member_metadata[b"header"], encoding=tf.encoding, errors="strict",
            )
            if tar_info.isfile():
                member_content = io.BytesIO(contents[0]["data"])
            else:
                member_content = io.BytesIO(b"")
            tf.addfile(tar_info, member_content)


def run_pristine(
    storage: StorageInterface,
    revision_swhid: SWHID,
    intermediate_path: str,
    target_path: str,
):
    tar_metadata = get_tar_metadata(storage, revision_swhid)

    if tar_metadata[b"pristine"] is None:
        return

    ext = tar_metadata[b"pristine"][b"type"].decode()
    assert ext in ("gz", "bz2", "xz")

    with open(target_path, "wb") as fd:
        proc = subprocess.run(
            ["pristine-" + ext, "gen" + ext, "-", intermediate_path],
            input=tar_metadata[b"pristine"][b"delta"],
            stdout=fd,
        )

    assert proc.returncode == 0, proc


def check_files_equal(source_path, target_path):
    with open(source_path, "rb") as source_fd, open(target_path, "rb") as target_fd:
        while True:
            source_chunk = source_fd.read(512)
            target_chunk = target_fd.read(512)
            if source_chunk != target_chunk:
                return False
            if not source_chunk:
                return True


def run_one(source_path: str, target_path: Optional[str] = None):
    storage = get_storage("memory")

    print(f"{source_path}: ingesting")
    revision_swhid = ingest_tarball(storage, source_path)

    print(f"{source_path}: reproducing")
    tar_metadata = get_tar_metadata(storage, revision_swhid)
    original_filename = tar_metadata[b"filename"]

    if target_path is None:
        target_file = tempfile.NamedTemporaryFile(suffix=original_filename)
        target_path = target_file.name

    intermediate_file = tempfile.NamedTemporaryFile(suffix=".tar")
    intermediate_path = intermediate_file.name

    generate_tarball(storage, revision_swhid, intermediate_path)

    if check_files_equal(source_path, intermediate_path):
        print(f"{source_path} is reproducible without pristine-tar")
    else:
        run_pristine(storage, revision_swhid, intermediate_path, target_path)

        if check_files_equal(source_path, target_path):
            print(f"{source_path} is reproducible after pristine-tar")
        else:
            print(f"{source_path} is not reproducible")


@click.group()
def cli():
    pass


@cli.command()
@click.option(
    "--diffoscope", default=False, is_flag=True, help="Run diffoscope before exiting."
)
@click.argument("source_path")
@click.argument("target_path", default="")
def single(diffoscope, source_path, target_path):
    run_one(source_path, target_path)

    if diffoscope:
        proc = subprocess.run(["diffoscope", source_path, target_path])
        exit(proc.returncode)


@cli.command()
@click.argument("source_paths", nargs=-1)
def many(source_paths):
    for source_path in source_paths:
        run_one(source_path)


if __name__ == "__main__":
    exit(cli())
