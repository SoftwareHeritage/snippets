# Copyright (C) 2023  The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information

import click
import gzip
import yaml
import logging

from pathlib import Path

from azure.storage.blob import ContainerClient as Client
from azure.core.exceptions import ResourceExistsError

logger = logging.getLogger(__name__)


DEFAULT_CONFIG_FILE = "~/.config/swh-azure/config.yaml"

AZURE_CONNECTION_STRING = """DefaultEndpointsProtocol=https;\
AccountName={account_name};\
AccountKey={account_key};\
BlobEndpoint={blob_endpoint};"""


SRC_CONTAINER_NAME = "contents"
DST_CONTAINER_NAME = f"{SRC_CONTAINER_NAME}-uncompressed"


@click.command()
@click.option("-C", "--config-file",
              default=DEFAULT_CONFIG_FILE,
              type=click.Path(exists=True, readable=True),
              help="Configuration with azure account credentials")
@click.option("-w", "--with-already-migrated-hash-file",
              "already_migrated_hashes_file",
              type=click.Path(exists=True, readable=True),
              help="List of hashes of blob already pushed")
@click.option("--debug/--no-debug",
              default=False,
              help="Debug")
def migrate(config_file, already_migrated_hashes_file, debug):
    logger.setLevel(logging.INFO if not debug else logging.DEBUG)

    if already_migrated_hashes_file:
        # Retrieve data already migrated if provided
        f = Path(already_migrated_hashes_file)
        hash_already_migrated = set(filter(lambda x: x, f.read_text().split('\n')))
    else:
        hash_already_migrated = set()

    config = yaml.safe_load(Path(config_file).read_bytes())

    account_name = config["account_name"]
    account_key = config["account_key"]
    blob_endpoint = f"https://{account_name}.blob.core.windows.net/"

    conn_str = AZURE_CONNECTION_STRING.format(account_name=account_name,
                                              account_key=account_key,
                                              blob_endpoint=blob_endpoint)

    src_container_client = Client.from_connection_string(conn_str, SRC_CONTAINER_NAME)
    dst_container_client = Client.from_connection_string(conn_str, DST_CONTAINER_NAME)

    hash_already_migrated = hash_already_migrated if hash_already_migrated else set()
    count = 0
    for blob in src_container_client.list_blobs():
        count += 1
        if blob.name in hash_already_migrated:
            # Skipping already pushed blob
            continue
        try:
            blob_data = src_container_client.download_blob(blob)
            logger.debug("Push uncompress blob <%s> in container <%s>",
                         blob.name, DST_CONTAINER_NAME)
            dst_container_client.upload_blob(blob, gzip.decompress(blob_data.readall()))
            # Output what's been migrated so it can be flushed in a file for ulterior
            # runs
            print(blob.name)
        except ResourceExistsError:
            # Somehow, we did not see we already pushed it but azure tells us as much so
            # let's skip it (instead of breaking the loop)
            pass
        hash_already_migrated.add(blob.name)

    assert count != len(hash_already_migrated)

if __name__ == "__main__":
    logging.basicConfig()
    migrate()
