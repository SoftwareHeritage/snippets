#!/usr/bin/env python3

"""Journal client dumped disk representation analysis.

"""

import logging
import click
import os
from os.path import join

from swh.storage import get_storage
from pathlib import Path
import shutil

# For eval_read function
import datetime  # noqa
from swh.model.swhids import *  # noqa
from swh.model.model import *  # noqa
# Beware the ObjectType import in both module ^
from swh.core.utils import grouper

from get_journal_check_and_replay import (
    configure_obj_get, is_iterable, search_for_obj_model, configure_logger, read_config
)


logger = logging.getLogger(__name__)


def eval_read(path, with_warning=True):
    #from swh.model.model import *
    if not os.path.exists(path):
        return None
    with open(path, "r") as f:
        data = f.read()
        try:
            res = eval(data)
        except SyntaxError:
            if with_warning:
                logger.info(
                    "### WARNING: path <%s> holds some syntax error. \n"
                    "### WARNING: It's probably an old bug in the initial run "
                    "(e.g. lazyness issue ended up with 'itertool._tee' entry in files)",
                    path
                )
                logger.info("### WARNING: data: %s", data)

            # Could not read the representation, because of previous issue in data (e.g.
            # itertool.tee)
            res = None

    return res


def file_rep_paths(dir_path):
    """"Compute representation filepaths on disk independently from their existence."""
    dir_path_str = str(dir_path)
    cass_rep_path = join(dir_path_str, "cassandra_representation")
    jn_rep_path = join(dir_path_str, "journal_representation")
    pg_rep_path = join(dir_path_str, "postgresql_representation")

    return cass_rep_path, jn_rep_path, pg_rep_path


def is_representation_directory(dir_path):
    """Is the directory a folder holding representation file on disk?"""
    return any(map(os.path.exists, file_rep_paths(dir_path)))


def from_path_to_rep(dir_path, with_warning=True):
    """Compute the object representation from the dir_path."""
    cass_rep_path, jn_rep_path, pg_rep_path = file_rep_paths(dir_path)
    jn_rep = eval_read(jn_rep_path, with_warning=with_warning)
    cass_rep = eval_read(cass_rep_path, with_warning=with_warning)
    pg_rep = eval_read(pg_rep_path, with_warning=with_warning)
    return jn_rep, cass_rep, pg_rep


def printable_rep(obj_rep):
    """Prepare a printable representation of obj_rep."""
    if hasattr(obj_rep, "to_dict"):
        # assumed a model object
        res = obj_rep.to_dict()
    else:
        # could be None, a list or a dict, print as is
        res = obj_rep
    return res


def print_reps(jn_rep, cass_rep, pg_rep):
    from pprint import pprint  # noqa
    print("Journal representation:")
    pprint(printable_rep(jn_rep))
    print("Cassandra representation:")
    pprint(printable_rep(cass_rep))
    print("Postgresql representation:")
    pprint(printable_rep(pg_rep))


def filter_path_to_delete(dir_path, cs_storage, pg_storage):
    """Yield swhid path to delete when the swhid is found in cassandra."""
    dir_path = Path(dir_path)
    otype = dir_path.name
    logger.info("Scan folder <%s> for swhid like entries", dir_path)
    for _, swhids, _ in os.walk(dir_path, topdown=False):
        for swhid in swhids:
            swhid_path = dir_path / Path(swhid)

            jn_rep, _, _ = from_path_to_rep(swhid_path, with_warning=False)

            logger.debug("Check swhid <%s> folder", swhid)
            if jn_rep is None:
                logger.info("Journal representation of <%s> is None, skipping...", swhid)
                continue

            obj_mdl, truncate_objmdl_fn, is_equal_fn, cs_get, _ = configure_obj_get(
                otype, jn_rep, cs_storage, pg_storage
            )

            cs_obj = cs_get()
            if not cs_obj:
                logger.debug("obj <%s> is indeed missing, do nothing.", swhid)
                # It's indeed missing, do nothing
                continue

            truncated_obj_model = truncate_objmdl_fn(obj_mdl)
            iterable = is_iterable(cs_obj)

            if iterable:
                logger.debug("swhid <%s> object found is an iterable", swhid)
                # List of Objects found, looking for unique object in list
                cs_obj, _ = search_for_obj_model(
                    is_equal_fn, truncated_obj_model, cs_obj
                )

            if cs_obj is not None and is_equal_fn(cs_obj, truncated_obj_model):
                logger.debug("obj <%s> was found in cassandra, mark for removal", swhid)
                # It's actually present in cassandra, it's a false negative, we need to drop the representation
                yield swhid_path
                continue


@click.command()
@click.option(
    "--config-file",
    "-C",
    default=None,
    type=click.Path(
        exists=True,
        dir_okay=False,
    ),
    help=(
        "Configuration file. This has a higher priority than SWH_CONFIG_FILENAME "
        "environment variable if set."
    ),
)
@click.option(
    "--batch-removal",
    "-b",
    default=100,
    help=(
        "Batch size of the number of objects to remove"
    ),
)
@click.option(
    "--debug",
    is_flag=True,
    default=False,
    help="Debug mode"
)
@click.option(
    "--dry-run/--no-dry-run",
    is_flag=True,
    default=False,
    help="Dry-run mode"
)
@click.option(
    "--dir-path",
    "-d",
    required=True,
    type=click.Path(
        exists=True,
        dir_okay=True,
        file_okay=False,
    ),
    help=(
        "Path of objects to analyze"
    ),
)
def main(config_file, dry_run, debug, dir_path, batch_removal):
    configure_logger(logger, debug)

    if is_representation_directory(dir_path):
        print_reps(*from_path_to_rep(dir_path))
    else:
        # Read the configuration out of the swh configuration file
        config = read_config(config_file)
        cs_storage = get_storage("cassandra", **config["cassandra"])
        pg_storage = get_storage("postgresql", **config["postgresql"])

        group_swhids_to_delete = grouper(
            filter_path_to_delete(dir_path, cs_storage, pg_storage),
            n=batch_removal
        )
        for swhids_to_delete in group_swhids_to_delete:
            for swhid_path in swhids_to_delete:
                logger.info(
                    "%srm -rv %s",
                    "**DRY_RUN** - " if dry_run else "",
                    swhid_path
                )
                if not dry_run:
                    shutil.rmtree(swhid_path)


if __name__ == "__main__":
    main()
