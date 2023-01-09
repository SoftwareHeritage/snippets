#!/usr/bin/env python3

from __future__ import annotations

import logging
import os
import sys
from collections import defaultdict
from itertools import zip_longest

import click
from phabricator import APIError, Phabricator

import gitlab

logger = logging.getLogger(__name__)


def grouper(iterable, n, *, incomplete="fill", fillvalue=None):
    "Collect data into non-overlapping fixed-length chunks or blocks"
    # grouper('ABCDEFG', 3, fillvalue='x') --> ABC DEF Gxx
    # grouper('ABCDEFG', 3, incomplete='strict') --> ABC DEF ValueError
    # grouper('ABCDEFG', 3, incomplete='ignore') --> ABC DEF
    args = [iter(iterable)] * n
    if incomplete == "fill":
        return zip_longest(*args, fillvalue=fillvalue)
    if incomplete == "strict":
        return zip(*args, strict=True)
    if incomplete == "ignore":
        return zip(*args)
    else:
        raise ValueError("Expected fill, strict, or ignore")


def get_phabricator(host: Optional[str], token: Optional[str]):
    # uses information from ~/.arcrc if the token or host argument are None
    phabricator = Phabricator(host=host, token=token)
    phabricator.connect()
    phabricator.update_interfaces()

    return phabricator


def load_mapping(mapping_filename):
    ret = defaultdict(dict)

    def push_mapping(item):
        if not item:
            return
        item_type = item.pop("type")[1:].lower()

        original_id = item.pop("original_id")

        if original_id in ret[item_type]:
            logger.warn("Duplicate mapping for %s %s: %s", item_type, original_id, item)

        ret[item_type][original_id] = item or True

    with open(mapping_filename, "r") as f:
        current_item = {}
        in_file = False
        for line in f.readlines():
            line = line.strip().rstrip(")")

            if not line:
                continue

            if line.startswith("#S(FORGERIE-GITLAB::MAPPED-ITEM"):
                in_file = False
                push_mapping(current_item)
                current_item = {}

                continue

            if line.startswith("#S(FORGERIE-GITLAB::MAPPED-FILE"):
                in_file = True

            if in_file:
                continue

            k, v = line.split(None, 1)
            if v == "NIL":
                continue

            key = k[1:].lower().replace("-", "_")

            if key in ("id", "iid", "project_id"):
                v = int(v)
            elif v[0] == v[-1] == '"':
                v = v[1:-1]

            current_item[key] = v
        else:
            # push the last item when the read ends
            push_mapping(current_item)

    return ret


def get_gitlab(gitlab_instance):
    gl = gitlab.Gitlab.from_config(gitlab_instance)
    gl.auth()

    return gl


def mark_phabricator_task_as_migrated(phabricator, task, gitlab_url, new_owner, do_it):
    transactions = []

    # Set owner/assignee to `gitlab-migration`
    transactions.append(
        {
            "type": "owner",
            "value": new_owner,
        }
    )

    # Add migration comment
    transactions.append(
        {
            "type": "comment",
            "value": f"[[ {gitlab_url} | This task has been migrated to GitLab. ]]",
        }
    )

    # Set status to migrated
    transactions.append(
        {
            "type": "status",
            "value": "migrated",
        }
    )

    if logger.isEnabledFor(logging.DEBUG):
        for transaction in transactions:
            logger.debug(
                "For task %s: %s -> %s",
                task["id"],
                transaction["type"],
                transaction["value"],
            )

    if do_it:
        logger.info("Marking task T%s migrated to %s", task["id"], gitlab_url)
        phabricator.maniphest.edit(
            objectIdentifier=task["phid"], transactions=transactions
        )


@click.command()
@click.option(
    "--gitlab",
    "-g",
    "gitlab_instance",
    help="Which GitLab instance to use, as configured in the python-gitlab config",
)
@click.option(
    "--phabricator-token",
    "phabricator_token",
    help="Phabricator API token",
)
@click.option(
    "--phabricator-host",
    "phabricator_host",
    help="Phabricator host",
)
@click.option(
    "--allowed-status",
    "-s",
    "allowed_statuses",
    help="Allowed task statuses",
    multiple=True,
    default=[],
)
@click.option(
    "--do-it",
    "do_it",
    is_flag=True,
    help="Actually perform the operations",
)
@click.argument("mapping_file")
def cli(
    gitlab_instance,
    phabricator_token,
    phabricator_host,
    allowed_statuses,
    do_it,
    mapping_file,
):
    phab = get_phabricator(host=phabricator_host, token=phabricator_token)
    me = phab.user.whoami()
    if me.userName != "gitlab-migration":
        print("This script must be run as the gitlab-migration user!")
        sys.exit(2)

    gl = get_gitlab(gitlab_instance)

    mapping = load_mapping(mapping_file)

    maniphest_tasks = {}
    for group in grouper(mapping["ticket-completed"], n=20):
        task_ids = [int(tid) for tid in group if tid]
        task_group = phab.maniphest.search(constraints={"ids": task_ids})
        for task in task_group["data"]:
            maniphest_tasks[task["id"]] = task

    for task_id in mapping["ticket-completed"]:
        phab_task_id = int(task_id)

        if phab_task_id not in maniphest_tasks:
            logger.warning("Cannot act on Phabricator task %s, skipping", phab_task_id)
            continue

        phab_task_status = maniphest_tasks[phab_task_id]["fields"]["status"]["value"]

        if phab_task_status == "migrated":
            logger.debug("Already migrated Phabricator task %s, skipping", phab_task_id)
            continue

        if allowed_statuses and phab_task_status not in allowed_statuses:
            logger.debug(
                "Phabricator task %s has status %s, skipping",
                phab_task_id,
                phab_task_status,
            )
            continue

        mapped_task = mapping["ticket"].get(task_id)
        if not mapped_task:
            logger.warning("Missing mapping for completed ticket %s ?!", task_id)
            continue
        gl_project = gl.projects.get(mapped_task["project_id"])
        gl_issue = gl_project.issues.get(mapped_task["iid"])

        try:
            mark_phabricator_task_as_migrated(
                phabricator=phab,
                task=maniphest_tasks[phab_task_id],
                gitlab_url=gl_issue.web_url,
                new_owner=me.phid,
                do_it=do_it,
            )
        except APIError:
            logger.exception("Could not migrate phabricator task %s", task_id)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG, format="%(asctime)s %(name)s:%(levelname)s %(message)s"
    )
    cli(auto_envvar_prefix="SWH")
