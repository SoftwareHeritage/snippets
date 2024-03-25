#!/usr/bin/env python3

"""Journal client dumped disk representation analysis.

"""

import click
import os
from os.path import join
from yaml import safe_load

# For eval_read function
import datetime  # noqa
from swh.model.swhids import *  # noqa
from swh.model.model import *  # noqa
# Beware the ObjectType import in both module ^

from typing import Any, Dict, Optional


def eval_read(path):
    #from swh.model.model import *
    if not os.path.exists(path):
        return None
    with open(path, "r") as f:
        data = f.read()
        try:
            res = eval(data)
        except SyntaxError:
            print(f"### WARNING: path <{path}> holds some syntax error. \n"
                  "### WARNING: It's probably an old bug in the initial run "
                  "(e.g. lazyness issue ended up with 'itertool._tee' entry in files)")
            print(f"### WARNING: data: {data}")
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


def from_path_to_rep(dir_path):
    """Compute the object representation from the dir_path."""
    cass_rep_path, jn_rep_path, pg_rep_path = file_rep_paths(dir_path)
    jn_rep = eval_read(jn_rep_path)
    cass_rep = eval_read(cass_rep_path)
    pg_rep = eval_read(pg_rep_path)
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


def read_config(config_file: Optional[Any] = None) -> Dict:
    """Read configuration from config_file if provided, from the SWH_CONFIG_FILENAME if
    set or fallback to the DEFAULT_CONFIG.

    """
    from os import environ

    if not config_file:
        config_file = environ.get("SWH_CONFIG_FILENAME")

    if not config_file:
        raise ValueError("You must provide a configuration file.")

    with open(config_file) as f:
        data = f.read()
        config = safe_load(data)

    return config


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
def main(config_file, dir_path):
    if is_representation_directory(dir_path):
        print_reps(*from_path_to_rep(dir_path))
    else:
        # TODO
        pass


if __name__ == "__main__":
    main()
