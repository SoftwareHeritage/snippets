# Copyright (C) 2023-2024  The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information

"""Tools to migrate old vault gzip blobs (in a given blobstorage) by unzipping the blobs
and push them to another blobstorage.

"""

import click
import gzip
import yaml
import logging

from pathlib import Path

from collections import defaultdict

from typing import Optional, Union
from datetime import datetime, timezone
from dateutil.parser import parse

from azure.storage.blob import ContainerClient as Client
from azure.core.exceptions import ResourceExistsError

logger = logging.getLogger(__name__)


DEFAULT_CONFIG_FILE = "~/.config/swh-azure/config.yaml"
# Expected format of the configuration file:
# account_name: accountnamewithoutseparator
# account_key: accountkey
# src_container_name: container-name
# dst_container_name: other-container-name

AZURE_CONNECTION_STRING = """DefaultEndpointsProtocol=https;\
AccountName={account_name};\
AccountKey={account_key};\
BlobEndpoint={blob_endpoint};"""


def parse_date(date_str: Optional[Union[datetime, str]]) -> Optional[datetime]:
    """Convert visit date from either None, a string or a datetime to either None or
    datetime.

    """
    if date_str is None:
        return None

    if isinstance(date_str, datetime):
        return date_str

    if date_str == "now":
        return datetime.now(tz=timezone.utc)

    if isinstance(date_str, str):
        date = parse(date_str)
        if date.tzinfo is None:
            date = date.replace(tzinfo=timezone.utc)
        return date

    raise ValueError(f"invalid visit date {date_str!r}")


MAGIC_DICT = {
    b'\x1f\x8b\x08': "gz",
    b'\x42\x5a\x68': "bz2",
    b'\x50\x4b\x03\x04': "zip"
}

MAX_LEN = max(len(x) for x in MAGIC_DICT)


class UncompressedContent(ValueError):
    """An uncompressed event"""
    pass


def file_type(fp):
    """Given a filehandle to read from, determine the filetype. Raise when the
    compression format (amongst gz, bz2, zip) is not one of those supported format (and
    consider the file uncompressed).

    """
    file_start = fp.read(MAX_LEN)
    if hasattr(fp, "seek"):  # usual python fp have this
        fp.seek(0)
    if hasattr(fp, "_offset"):  # Azure BlobData have hidden internal _offset
        fp._offset = 0

    for magic, filetype in MAGIC_DICT.items():
        if file_start.startswith(magic):
            return filetype
    raise UncompressedContent("Not compressed")


@click.command()
@click.option("-C", "--config-file",
              default=DEFAULT_CONFIG_FILE,
              type=click.Path(exists=True, readable=True),
              help="Configuration with azure account credentials")
@click.option("-w", "--with-already-migrated-hash-file",
              "already_migrated_hashes_file",
              type=click.Path(exists=True, readable=True),
              help="List of hashes of blob already pushed")
@click.option("-s", "--since",
              "since_date_str",
              help="The optional date from which the listing blobs should start")
@click.option("--debug/--no-debug",
              default=False,
              help="Debug")
@click.option("-l", "--limit",
              default=None,
              type=click.INT,
              help="Max number of files to process")
@click.option("--dry-run/--no-dry-run",
              default=False,
              help="Dry Run mode. Read fs but do not write to blobstorage")
@click.option("--just-count/--no-just-count",
              default=False,
              help="Just count blobs grouping by compression nature")
def migrate(config_file, already_migrated_hashes_file, debug, since_date_str, limit, dry_run, just_count):
    logger.setLevel(logging.INFO if not debug else logging.DEBUG)

    since_date = parse_date(since_date_str) if since_date_str else None

    if already_migrated_hashes_file:
        # Retrieve data already migrated if provided
        f = Path(already_migrated_hashes_file)
        hash_already_migrated = set(filter(lambda x: x, f.read_text().split('\n')))
    else:
        hash_already_migrated = set()

    config = yaml.safe_load(Path(config_file).read_bytes())

    account_name = config["account_name"]
    account_key = config["account_key"]
    src_container_name = config["src_container_name"]
    dst_container_name = config["dst_container_name"]
    blob_endpoint = f"https://{account_name}.blob.core.windows.net/"

    conn_str = AZURE_CONNECTION_STRING.format(account_name=account_name,
                                              account_key=account_key,
                                              blob_endpoint=blob_endpoint)

    src_container_client = Client.from_connection_string(conn_str, src_container_name)
    dst_container_client = Client.from_connection_string(conn_str, dst_container_name)

    hash_already_migrated = hash_already_migrated if hash_already_migrated else set()
    count = 0

    all_blobs = src_container_client.list_blobs()
    if since_date:
        all_blobs = (blob for blob in all_blobs if blob["creation_time"] >= since_date)

    if just_count:
        all_blobs = list(all_blobs)
        count_all_blobs = len(all_blobs)
        count_types = defaultdict(int)

    overwrite = src_container_name == dst_container_name

    count_global = 0
    for blob in all_blobs:
        if limit and count >= limit:
            break
        if blob.name in hash_already_migrated:
            # Skipping already pushed blob
            continue
        try:
            blob_data = src_container_client.download_blob(blob)
            file_type_blob = file_type(blob_data)
            if just_count:
                count_global += 1
                count_types[file_type_blob] += 1
            elif file_type_blob == "gz":
                count += 1
                # belt and suspenders: ensure we did not already migrated the data
                # if already migrated, these dates will differ while they match at
                # creation time
                if blob.creation_time == blob.last_modified:
                    logger.debug("%sPush uncompressed blob <%s> in container <%s>",
                                 "** DRY RUN ** " if dry_run else "", blob.name, dst_container_name)
                    logger.debug("%sBlob created on <%s>, last modified on <%s>",
                                 "** DRY RUN ** " if dry_run else "", blob.creation_time, blob.last_modified)
                    if not dry_run:
                        # Beware: if the configuration use the same src and destination
                        # blobstorages this will overwrite the remote blob
                        dst_container_client.upload_blob(blob, gzip.decompress(blob_data.readall()),
                                                         overwrite=overwrite)
                        # Output what's been migrated so it can be flushed in a file for
                        # ulterior runs
                        print(blob.name)
            else:
                logger.debug("########### %sblob <%s> with filetype <%s> detected",
                             "** DRY RUN ** " if dry_run else "", blob.name, file_type_blob)
        except UncompressedContent:
            if just_count:
                count_types["uncompressed"] += 1
            # Good, we skip it.
            pass
        except ResourceExistsError:
            # Somehow, we did not see we already pushed it but azure tells us as much so
            # let's skip it (instead of breaking the loop)
            pass
        hash_already_migrated.add(blob.name)

        if debug and just_count and count_global % 100 == 0:
            percent = 100.0 * count_global / count_all_blobs
            print(f"Counter per types: {dict(count_types)} - Completion: {percent:.2f}%" )

    if debug == 0 and just_count:
        print("Counter per types:", dict(count_types))

if __name__ == "__main__":
    logging.basicConfig()
    migrate()
