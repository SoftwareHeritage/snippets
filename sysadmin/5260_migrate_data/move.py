#!/usr/bin/env python

"""Script to move contents from objstorage storage1.staging to other db1.staging.

The gist of the algo is to try and copy objects (contents) from the source objstorage to
the destination objstorage out of a object ids (sha1) read from the stdin [1]. It does a
bunch of checks along the way (from already moved, presence check in source objstorage,
corruption check, existence check in the destination objstorage, ...). If any issues
during those checks, it logs the error and continues with the other objects. When the
move is done, an entry is logged in a manifest of moved objects.

The script is idempotent and can be called multiple times with the same set of inputs.

[1]
```
2024-04-24 11:37:51 swh@db1:5432 λ \copy (select encode(sha1, 'hex') from content
  tablesample system (0.1) limit 1000000) to '/var/tmp/content-sha1-sample';
COPY 1000000
Time: 329605.469 ms (05:29.605)
````

"""

import click
import sys
import os
import logging

from swh.objstorage.exc import ObjNotFoundError
from swh.objstorage.factory import get_objstorage
from swh.model.model import Content
from swh.model.hashutil import hash_to_hex
from typing import Set


logger = logging.getLogger(__name__)

RETRY_ADD_NUMBER = 3


def configure_logger(logger, debug_flag):
    """Configure logger according to environment variable or debug_flag."""
    FORMAT = "[%(asctime)s] %(message)s"
    logging.basicConfig(format=FORMAT)
    if "LOG_LEVEL" in os.environ:
        log_level_str = os.environ["LOG_LEVEL"].upper()
    elif debug_flag:
        log_level_str = "DEBUG"
    else:
        log_level_str = "INFO"

    log_level = getattr(logging, log_level_str)
    logger.setLevel(log_level)


def init_moved_objects(already_moved_filepaths: str) -> Set:
    """Initialize objects already moved from a list of filepaths."""
    moved = set()
    for manifest_moved_filepath in already_moved_filepaths:
        if os.path.exists(manifest_moved_filepath):
            with open(manifest_moved_filepath, "r") as f:
                moved.update(line.rstrip() for line in f.readlines())
    return moved


@click.command()
@click.option(
    "--debug", is_flag=True, default=False, help="Debug mode (be more verbose)"
)
@click.option(
    "--dry-run/--no-dry-run", is_flag=True, default=False, help="Dry-run mode"
)
@click.option(
    "--cleanup",
    is_flag=True,
    default=False,
    help="Do the clean up (does nothing in dry-run)",
)
@click.option(
    "--log-period",
    "-p",
    required=False,
    default=1000,
    help="Add log progression each <log-period> content",
)
@click.option(
    "--basedir",
    "-b",
    required=False,
    type=click.Path(
        exists=True,
        dir_okay=True,
        file_okay=False,
    ),
    default="/srv/softwareheritage/objects/",
    help=("Base directory of objects to move"),
)
@click.option(
    "--manifest-moved",
    "-m",
    "manifest_moved_filepath",
    required=False,
    type=click.Path(
        exists=False,
        dir_okay=False,
        file_okay=True,
    ),
    default="/var/tmp/content-moved",
    help=("Manifest files holding the content id for content actually moved"),
)
@click.option(
    "--already-moved",
    "-a",
    "already_moved_filepaths",
    multiple=True,
    required=False,
    type=click.Path(
        exists=True,
        dir_okay=False,
        file_okay=True,
    ),
    default=list(),
    help=("Manifest files of ids already moved"),
)
def main(
    debug,
    dry_run,
    cleanup,
    basedir,
    log_period,
    manifest_moved_filepath,
    already_moved_filepaths,
):
    configure_logger(logger, debug)
    moved = init_moved_objects(already_moved_filepaths)
    # Objstorage we will read content to be moved to
    src = get_objstorage(
        cls="pathslicing",
        compression="gzip",
        slicing="0:1/1:5",
        root=basedir,
        # Allow removal when not in dry run mode
        allow_delete=not dry_run,
    )
    # the destination objstorage
    dst = get_objstorage(
        cls="remote", url="http://objstorage-db1-rw.internal.staging.swh.network"
    )

    total_moved = 0
    for i, line in enumerate(sys.stdin):
        copied = False
        cleaned = False
        line = line.rstrip()
        if line.startswith("/"):
            # line read are path
            obj_id = line.split("/")[-1]
        else:
            # assumed lines are sha1
            obj_id = line

        if obj_id in moved:
            logger.debug("Content <%s> already moved, skipping", obj_id)
            continue

        logger.debug("Content <%s> to copy from src to dst", obj_id)
        try:
            obj = src.get(obj_id)
        except ObjNotFoundError:
            log_with_status(
                logger.debug,
                f"Content <{obj_id}> not present in src objstorage",
                log_period,
                total_moved,
                i,
            )
            # The content chosen to be moved is not present in the src storage
            # (could be because it's in another objstorage)
            continue

        content = Content.from_data(obj)
        hashes = content.hashes()
        actual_hash = hash_to_hex(hashes["sha1"])
        if obj_id != actual_hash:
            log_with_status(
                logger.error,
                f"Mismatched hash <{obj_id}>, found <{actual_hash}>",
                log_period,
                total_moved,
                i,
            )
            continue
        # Try to write
        if dry_run:
            logger.info("** DRY-RUN** Write <%s> in destination objstorage.", obj_id)

        if not dry_run:
            for j in range(1, RETRY_ADD_NUMBER + 1):
                try:
                    dst.add(content.data, obj_id=hashes)
                    copied = True
                except Exception as e:
                    logger.error(
                        "Attempt %s/%s: Write <%s> in destination objstorage",
                        j,
                        RETRY_ADD_NUMBER,
                        obj_id,
                    )
                    logger.exception(e)
                else:
                    break
            else:
                log_with_status(
                    logger.error,
                    f"Failed to write object <{obj_id}> in destination objstorage",
                    log_period,
                    total_moved,
                    i,
                )
                continue

        if copied and cleanup:
            if dry_run:
                logger.info(
                    "** DRY-RUN** Clean up <%s> from the source objstorage", obj_id
                )
            else:
                # Ensure we are able to read the new copied content
                count_read = 0
                while True:
                    count_read += 1
                    try:
                        content_from_dst = dst.get(obj_id)
                    except Exception as e:
                        logger.error(
                            "Attempt %s: Read <%s>/♾: from destination objstorage",
                            count_read,
                            obj_id,
                        )
                        logger.exception(e)
                    else:
                        break

                content_copied = Content.from_data(content_from_dst)
                if content_copied == content:
                    src.delete(obj_id)
                    cleaned = True
                    moved.add(obj_id)
                else:
                    log_with_status(
                        logger.error,
                        f"Mismatched copy <{content}> (src] != <{content_copied}> (dst)",
                        log_period,
                        total_moved,
                        i,
                    )
                    continue

        if cleaned:
            with open(manifest_moved_filepath, "a") as f:
                f.write(f"{obj_id}\n")

        if copied and cleaned:
            total_moved += 1

        log_with_status(None, None, log_period, total_moved, i)

    logger.info("Totally moved %s contents out of %s content ids read", total_moved, i)


def log_with_status(logger_fn, msg, log_period, total_moved, i):
    if logger_fn and msg:
        logger_fn(msg)
    if i != 0 and i % log_period == 0:
        logger.info("Moved contents: %s / %s", total_moved, i)


if __name__ == "__main__":
    main()
