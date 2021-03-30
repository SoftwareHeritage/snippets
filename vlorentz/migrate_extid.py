#!/usr/bin/env python3

# Copyright (C) 2020-2021  The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information

"""This is an executable script to external identifiers from metadata in
the revision table to the new ExtID storage, with a linear scan of the whole
table
"""

import sys
import time
from typing import Any, Dict, Optional

import psycopg2

from swh.core.db import BaseDb
from swh.loader.package.debian.loader import DebianLoader
from swh.loader.package.archive.loader import ArchiveLoader
from swh.loader.package.cran.loader import CRANLoader
from swh.loader.package.npm.loader import NpmLoader, EXTID_TYPE as NPM_EXTID_TYPE
from swh.loader.package.nixguix.loader import NixGuixLoader
from swh.loader.package.pypi.loader import PyPILoader
from swh.model.hashutil import hash_to_bytes, hash_to_hex
from swh.model.identifiers import CoreSWHID, ObjectType
from swh.model.model import ExtID, Sha1Git
from swh.storage import get_storage
from swh.storage.migrate_extrinsic_metadata import REVISION_COLS

HG_EXTID_TYPE = "hg-nodeid"

DEBIAN_LOADER = DebianLoader(None, "http://does-not-matter.example/", None, None, None)
"""Dummy debian loader, we only need it to compute the extid"""

ARCHIVE_LOADER = ArchiveLoader(None, "http://does-not-matter.example/", [])
"""Dummy archive loader, we only need it to compute the extid"""


def handle_hg_row(revision_swhid: CoreSWHID, metadata: Dict) -> ExtID:
    nodeid = hash_to_bytes(metadata["node"])
    return ExtID(extid_type=HG_EXTID_TYPE, extid=nodeid, target=revision_swhid)


def handle_dsc_row(revision_swhid: CoreSWHID, metadata: Dict) -> ExtID:
    try:
        res = DEBIAN_LOADER.known_artifact_to_extid(metadata)
    except TypeError as e:
        if e.args == ("__init__() missing 1 required positional argument: 'md5sum'",):
            # ???
            return None
        else:
            raise
    if res:
        (extid_type, extid) = res
        return ExtID(extid_type=extid_type, extid=extid, target=revision_swhid)
    return None


def handle_tar_row(revision_swhid: CoreSWHID, metadata: Dict) -> Optional[ExtID]:
    import pprint

    # pprint.pprint(metadata)

    provider = metadata.get("extrinsic", {}).get("provider", "")
    package_source = metadata.get("package_source", {})
    package_source_url = package_source.get("url", "")

    original_artifacts = metadata.get("original_artifact")

    # Old loaders wrote a dict instead of a list
    if isinstance(original_artifacts, dict):
        original_artifacts = [original_artifacts]

    if original_artifacts:
        original_artifact = original_artifacts[0]
    else:
        original_artifact = {}

    url = original_artifact.get("url", "")

    if url.startswith("https://files.pythonhosted.org/") or provider.startswith(
        "https://pypi.org/pypi/"
    ):
        res = PyPILoader.known_artifact_to_extid(metadata)
        if res:
            (extid_type, extid) = res
            return ExtID(extid_type=extid_type, extid=extid, target=revision_swhid)

    if provider.startswith("https://replicate.npmjs.com/"):
        res = NpmLoader.known_artifact_to_extid(metadata)
        if res:
            (extid_type, extid) = res
            return ExtID(extid_type=extid_type, extid=extid, target=revision_swhid)

    if provider.startswith("https://cran.r-project.org/"):
        res = CRANLoader.known_artifact_to_extid(metadata)
        if res:
            (extid_type, extid) = res
            return ExtID(extid_type=extid_type, extid=extid, target=revision_swhid)

    if provider in (
        "https://nix-community.github.io/nixpkgs-swh/sources-unstable.json",
        "https://guix.gnu.org/sources.json",
    ):
        res = NixGuixLoader.known_artifact_to_extid(metadata)
        if res:
            (extid_type, extid) = res
            return ExtID(extid_type=extid_type, extid=extid, target=revision_swhid)

    if provider.startswith(("https://ftp.gnu.org/gnu/", "https://ftp.gnu.org/old-gnu/")):
        res = ARCHIVE_LOADER.known_artifact_to_extid(metadata)
        if res:
            (extid_type, extid) = res
            return ExtID(extid_type=extid_type, extid=extid, target=revision_swhid)

    if package_source_url.startswith("https://registry.npmjs.org/"):
        return ExtID(
            extid_type=NPM_EXTID_TYPE,
            extid=hash_to_bytes(package_source["sha1"]),
            target=revision_swhid,
        )

    if url.startswith("https://deposit.softwareheritage.org/") or provider.startswith("https://deposit.softwareheritage.org/") or "{http://www.w3.org/2005/Atom}client" in metadata or "@xmlns:codemeta" in metadata:
        # Deposits don't have ExtIDs
        return None

    if (
        "sha1_git" in original_artifact
        and "url" not in original_artifact
        and not provider
        and not package_source_url
    ):
        # Very old loader, doesn't tell where the package is coming from
        return None

    assert False, "\n" + pprint.pformat(metadata)

    return None


def handle_row(row: Dict[str, Any], storage, dry_run: bool):
    type_ = row["type"]

    if type_ in ("git", "svn"):
        return

    revision_swhid = CoreSWHID(object_type=ObjectType.REVISION, object_id=row["id"])
    metadata = row["metadata"]

    if type_ == "hg":
        extid = handle_hg_row(revision_swhid, metadata)
    elif type_ == "tar":
        extid = handle_tar_row(revision_swhid, metadata)
    elif type_ == "dsc":
        extid = handle_dsc_row(revision_swhid, metadata)
    else:
        assert False, f"revision {hash_to_hex(row['id'])} has unknown type: {type_}"

    if extid is not None:
        if dry_run:
            print(f"storing: {extid.extid_type}:{extid.extid.hex()} -> {extid.target}")
        else:
            storage.extid_add([extid])


def iter_revision_rows(storage_dbconn: str, first_id: Sha1Git):
    after_id = first_id
    failures = 0
    while True:
        try:
            storage_db = BaseDb.connect(storage_dbconn)
            with storage_db.cursor() as cur:
                while True:
                    cur.execute(
                        f"SELECT {', '.join(REVISION_COLS)} FROM revision "
                        f"WHERE id > %s AND metadata IS NOT NULL "
                        f"AND type IN ('hg', 'tar', 'dsc') "
                        f"ORDER BY id LIMIT 1000",
                        (after_id,),
                    )
                    new_rows = 0
                    for row in cur:
                        new_rows += 1
                        row_d = dict(zip(REVISION_COLS, row))
                        yield row_d
                    after_id = row_d["id"]
                    if new_rows == 0:
                        return
        except psycopg2.OperationalError as e:
            print(e)
            # most likely a temporary error, try again
            if failures >= 60:
                raise
            else:
                time.sleep(60)
                failures += 1


def main(storage_dbconn, storage_url, first_id, dry_run):
    storage = get_storage(
        "pipeline",
        steps=[
            {"cls": "buffer"},
            {"cls": "retry"},
            {
                "cls": "local",
                "db": storage_dbconn,
                "objstorage": {"cls": "memory", "args": {}},
            },
        ],
    )

    total_rows = 0
    for row in iter_revision_rows(storage_dbconn, first_id):
        handle_row(row, storage, dry_run)

        total_rows += 1

        if total_rows % 1000 == 0:
            percents = int.from_bytes(row["id"][0:4], byteorder="big") * 100 / (1 << 32)
            print(
                f"Processed {total_rows/1000000.:.2f}M rows "
                f"(~{percents:.1f}%, last revision: {row['id'].hex()})"
            )

    storage.flush()


if __name__ == "__main__":
    if len(sys.argv) == 3:
        (_, storage_dbconn, storage_url) = sys.argv
        first_id = "00" * 20
    elif len(sys.argv) == 4:
        (_, storage_dbconn, storage_url, first_id) = sys.argv
    else:
        print(f"Syntax: {sys.argv[0]} <storage_dbconn> <storage_url> [<first id>]")
        exit(1)

    main(storage_dbconn, storage_url, bytes.fromhex(first_id), True)
