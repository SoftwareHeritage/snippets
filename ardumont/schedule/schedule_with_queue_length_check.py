#!/usr/bin/env python3

# Copyright (C) 2017 The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information


from functools import partial
import os
import sys
import time
from typing import Any, Callable, Dict, Iterable, Iterator, List, Optional, Tuple

import click

from swh.core import config
from swh.scheduler import DEFAULT_CONFIG, get_scheduler
from swh.scheduler.celery_backend.config import app as main_app
from swh.scheduler.cli.utils import parse_options

MAX_WAITING_TIME = 10


def create_task_arguments(args: Tuple = (), kwargs: Dict = {}) -> Dict:
    return {"args": args, "kwargs": kwargs}


def lines_to_task_args(
    lines: Iterable[str],
    columns: List[str] = ["url"],
    postprocess: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None,
    **kwargs,
) -> Iterator[Dict[str, Any]]:
    for line in lines:
        values = line.strip().split()
        ret = dict(zip(columns, values))
        ret.update(kwargs)
        if postprocess:
            ret = postprocess(ret)
        yield create_task_arguments(kwargs=ret)


stdin_to_mercurial_tasks = partial(
    lines_to_task_args, lines=sys.stdin, columns=["origin_url", "archive_path"]
)
stdin_to_bitbucket_mercurial_tasks = partial(
    lines_to_task_args, lines=sys.stdin, columns=["url", "directory", "visit_date"]
)


def stdin_to_svn_tasks(type: str = "svn", **kwargs) -> Iterator[Dict]:
    """Generates from stdin the proper task argument for the loader-svn
       worker.

    Yields:
        expected dictionary of 'arguments' key

    """
    if type == "svn":
        yield from lines_to_task_args(lines=sys.stdin, columns=["url"], **kwargs)
    else:
        yield from lines_to_task_args(
            lines=sys.stdin,
            columns=["origin_url", "archive_path"],
            **kwargs,
        )


def update_git_task_kwargs(kwargs: Dict[str, Any]) -> Dict[str, Any]:
    """Create simple git task kwargs from an url."""

    ret = kwargs.copy()

    if "github.com" in ret["url"]:
        ret.update(
            {
                "lister_name": "github",
                "lister_instance_name": "github",
            }
        )

    return ret


stdin_to_git_normal_tasks = partial(
    lines_to_task_args,
    lines=sys.stdin,
    columns=["url"],
    postprocess=update_git_task_kwargs,
)


stdin_to_git_large_tasks = partial(
    stdin_to_git_normal_tasks,
    pack_size_bytes=34359738368,
    verify_certs=False,
)

ARGS_GENERATORS = {
    "load-svn-dump": partial(stdin_to_svn_tasks, type="dump"),
    "load-svn": stdin_to_svn_tasks,
    "load-mercurial-archive": partial(
        stdin_to_mercurial_tasks,
        visit_date="Tue, 3 May 2016 17:16:32 +0200",
    ),
    "load-mercurial": stdin_to_bitbucket_mercurial_tasks,
    "load-git-normal": stdin_to_git_normal_tasks,
    "load-git-large": stdin_to_git_large_tasks,
}


def queue_length_get(app, queue_name: str) -> Optional[int]:
    """Read the queue's current length.

    Args:
        app: Application
        queue_name: fqdn queue name to retrieve queue length from

    Returns:
        queue_name's length if any

    """
    try:
        queue_length = app.get_queue_length(queue_name)
    except Exception:
        queue_length = None
    return queue_length


@click.command(help="Read from stdin and send message to queue ")
@click.option("--queue-name-prefix", help="Prefix to add to the queue name if needed")
@click.option(
    "--threshold", help="Threshold for the queue", type=click.INT, default=1000
)
@click.option(
    "--waiting-time",
    help="Waiting time between checks",
    type=click.INT,
    default=MAX_WAITING_TIME,
)
@click.option("--dry-run", is_flag=True)
@click.argument(
    "task_type",
    nargs=1,
    required=True,
)
@click.argument(
    "options",
    nargs=-1,
)
@click.pass_context
def main(
    ctx,
    queue_name_prefix,
    threshold,
    waiting_time,
    dry_run,
    task_type,
    options,
    app=main_app,
):
    conf = config.read(os.environ["SWH_CONFIG_FILENAME"], DEFAULT_CONFIG)
    if "scheduler" not in conf:
        ctx.fail("scheduler config missing")

    scheduler = get_scheduler(**conf["scheduler"])

    scheduler_task_type = task_type
    scheduler_info = scheduler.get_task_type(scheduler_task_type)
    while not scheduler_info:
        print(f"Could not find task type {scheduler_task_type}")
        new_scheduler_task_type = scheduler_task_type.rsplit("-", 1)[0]
        if new_scheduler_task_type == scheduler_task_type:
            ctx.fail(f"Could not find scheduler task type for {task_type}")
        scheduler_task_type = new_scheduler_task_type
        scheduler_info = scheduler.get_task_type(scheduler_task_type)

    print(scheduler_info)

    celery_task_name = scheduler_info["backend_name"]
    if queue_name_prefix:
        queue_name = f"{queue_name_prefix}:{celery_task_name}"
    else:
        queue_name = celery_task_name

    if not threshold:
        threshold = scheduler_info.get("max_queue_length") or 1000

    task_fn = ARGS_GENERATORS.get(
        task_type, partial(lines_to_task_args, lines=sys.stdin, columns=["url"])
    )

    (extra_args, extra_kwargs) = parse_options(options)

    while True:
        throttled = False
        remains_data = False
        pending_tasks = []

        # we can send new tasks, compute how many we can send
        queue_length = queue_length_get(app, queue_name)
        if queue_length is not None:
            nb_tasks_to_send = threshold - queue_length
        else:
            nb_tasks_to_send = threshold

        if nb_tasks_to_send > 0:
            count = 0
            for _task in task_fn(**extra_kwargs):
                pending_tasks.append(_task)
                count += 1

                if count >= nb_tasks_to_send:
                    throttled = True
                    remains_data = True
                    break

            if not pending_tasks:
                # check for some more data on stdin
                if not remains_data:
                    # if no more data, we break to exit
                    break

            from kombu.utils.uuid import uuid

            for _task_args in pending_tasks:
                send_task_kwargs = dict(
                    name=celery_task_name,
                    task_id=uuid(),
                    args=tuple(_task_args["args"]) + tuple(extra_args),
                    kwargs=_task_args["kwargs"],
                    queue=queue_name,
                )
                if dry_run:
                    print("would call app.send_task with:", send_task_kwargs)
                else:
                    app.send_task(**send_task_kwargs)
                    print(_task_args)

        else:
            throttled = True

        if throttled:
            time.sleep(waiting_time)


if __name__ == "__main__":
    main()
