#!/usr/bin/env python3

"""Journal client dumped disk representation analysis.

"""

import click
import os
from os.path import join
from yaml import safe_load

# For eval_read function
import datetime  # noqa
from swh.model.model import *  # noqa
from swh.model.swhids import *  # noqa

from typing import Any, Dict, Optional


def eval_read(path):
    #from swh.model.model import *
    if not os.path.exists(path):
        return None
    with open(path, "r") as f:
        return eval(f.read())


def from_path_to_rep(dir_path):
    dir_path_str = str(dir_path)
    cass_rep_path = join(dir_path_str, "cassandra_representation")
    jn_rep_path = join(dir_path_str, "journal_representation")
    pg_rep_path = join(dir_path_str, "postgresql_representation")
    jn_rep = eval_read(jn_rep_path)
    cass_rep = eval_read(cass_rep_path)
    pg_rep = eval_read(pg_rep_path)
    return jn_rep, cass_rep, pg_rep


def print_reps(jn_rep, cass_rep, pg_rep):
    from pprint import pprint  # noqa
    print("Journal representation:")
    pprint(jn_rep)
    print("Cassandra representation:")
    pprint(cass_rep.to_dict() if cass_rep else None)
    print("Postgresql representation:")
    pprint(pg_rep.to_dict() if pg_rep else None)


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
    # dir_path = "/volume/production-check-cassandra/journal_only/origin_visit/b605c6f290ec146d537b193a03a7ea55571f177a"
    print_reps(*from_path_to_rep(dir_path))


if __name__ == "__main__":
    main()
