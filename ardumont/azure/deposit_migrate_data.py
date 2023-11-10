# Copyright (C) 2023  The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information

"""Tools to migrate deposit archives stored in the directory MEDIA_ROOT with a specific
arborescence /path/<client_id>/YYYYDDMM-HHmmss.ms/*.* to an azure blobstorage (dedicated
to deposit).

"""

import click
import os
import yaml
import logging

from pathlib import Path

from azure.storage.blob import ContainerClient as Client
from azure.core.exceptions import ResourceExistsError

logger = logging.getLogger(__name__)


DEFAULT_CONFIG_FILE = "~/.config/swh-azure/config.yaml"
# Expected format of the configuration file:
# account_name: accountnamewithoutseparator
# account_key: accountkey
# container_name: container-name

AZURE_CONNECTION_STRING = """DefaultEndpointsProtocol=https;\
AccountName={account_name};\
AccountKey={account_key};\
BlobEndpoint={blob_endpoint};"""


@click.command()
@click.option("-C", "--config-file",
              default=DEFAULT_CONFIG_FILE,
              type=click.Path(exists=True, readable=True),
              help="Configuration with azure account credentials")
@click.option("-p", "--path-to-files-to-migrate",
              "path_files_to_migrate",
              type=click.Path(exists=True, readable=True),
              help="Path of directory to scan to list files to migrate")
@click.option("-a", "--already-migrated-files",
              "already_migrated_files",
              type=click.Path(exists=True, readable=True),
              help="List of files already migrated")
@click.option("-l", "--limit",
              default=None,
              type=click.INT,
              help="Max number of files to process")
@click.option("--debug/--no-debug",
              default=False,
              help="Debug")
@click.option("--dry-run/--no-dry-run",
              default=False,
              help="Dry Run mode. Read fs but do not write to blobstorage")
def migrate(config_file, path_files_to_migrate, already_migrated_files, limit, debug,
            dry_run):
    logger.setLevel(logging.INFO if not debug else logging.DEBUG)

    if already_migrated_files:
        # Retrieve data already migrated if provided
        f = Path(already_migrated_files)
        already_migrated = set(filter(lambda x: x, f.read_text().split('\n')))
    else:
        already_migrated = set()

    config = yaml.safe_load(Path(config_file).read_bytes())

    account_name = config["account_name"]
    account_key = config["account_key"]
    blob_endpoint = f"https://{account_name}.blob.core.windows.net/"

    conn_str = AZURE_CONNECTION_STRING.format(account_name=account_name,
                                              account_key=account_key,
                                              blob_endpoint=blob_endpoint)

    container_name = config["container_name"]
    container_client = Client.from_connection_string(conn_str, container_name)

    already_migrated = already_migrated if already_migrated else set()
    count = 0

    for (dirpath, dirnames, filenames) in os.walk(path_files_to_migrate):
        if limit and count >= limit:
            break
        for filename in filenames:
            blob_path = Path(dirpath) / Path(filename)
            assert blob_path.exists()
            count += 1
            blob_path_str = blob_path.as_posix()
            blob_filename = blob_path_str.lstrip(path_files_to_migrate)
            if blob_path.exists() and blob_filename in already_migrated:
                # Skipping already pushed blob
                continue
            try:
                logger.debug("Push blob <%s> in container <%s>",
                             blob_filename, container_name)
                if not dry_run:
                    container_client.upload_blob(blob_filename, Path(blob_path).read_bytes())
                # Output what's been migrated so it can be flushed in a file for
                # ulterior runs
                print(blob_filename)
            except ResourceExistsError:
                # Somehow, we did not see we already pushed it but azure tells us as
                # much so let's skip it (instead of breaking the loop)
                pass
            already_migrated.add(blob_filename)

    assert len(already_migrated) == (limit or count)


if __name__ == "__main__":
    logging.basicConfig()
    migrate()
