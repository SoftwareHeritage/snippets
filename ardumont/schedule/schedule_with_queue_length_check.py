#!/usr/bin/env python3

# Copyright (C) 2017-2022  The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information


import click
import sys
import time

from typing import Dict, Optional

from swh.scheduler.celery_backend.config import app as main_app


MAX_WAITING_TIME = 10


def stdin_to_mercurial_tasks(batch_size):
    """Generates from stdin the proper task argument for the
       loader-mercurial worker.

    Args:
        batch_size (int): Not used

    Yields:
        expected dictionary of 'arguments' key

    """
    for line in sys.stdin:
        line = line.rstrip()
        origin_url, archive_path = line.split(" ")
        yield {
            "arguments": {
                "args": [],
                "kwargs": {
                    "origin_url": origin_url,
                    "archive_path": archive_path,
                    "visit_date": "Tue, 3 May 2016 17:16:32 +0200",
                },
            },
        }


def stdin_to_bitbucket_mercurial_tasks(batch_size):
    """Generates from stdin the proper task argument for the
       bitbucket loader-mercurial worker.

    Args:
        batch_size (int): Not used

    Yields:
        expected dictionary of 'arguments' key

    """
    for line in sys.stdin:
        line = line.rstrip()
        origin_url, directory, visit_date_day, visit_date_hour = line.split(" ")
        visit_date = " ".join([visit_date_day, visit_date_hour])
        yield {
            "arguments": {
                "args": [],
                "kwargs": {
                    "url": origin_url,
                    "directory": directory,
                    "visit_date": visit_date,
                },
            },
        }


def stdin_to_svn_tasks(batch_size, type="svn"):
    """Generates from stdin the proper task argument for the loader-svn
       worker.

    Args:
        batch_size (int): Not used

    Yields:
        expected dictionary of 'arguments' key

    """
    for line in sys.stdin:
        line = line.rstrip()
        origin_url, path = line.split(" ")
        kwargs = {
            "visit_date": "Tue, 3 May 2016 17:16:32 +0200",
            "start_from_scratch": True,
        }
        if type == "svn":
            kwargs.update(
                {
                    "svn_url": origin_url,
                }
            )
        else:
            kwargs.update(
                {
                    "archive_path": path,
                    "origin_url": origin_url,
                }
            )
        yield {
            "arguments": {
                "args": [],
                "kwargs": kwargs,
            },
        }


def stdin_to_git_large_tasks(batch_size, type="git"):
    """Generates from stdin the proper task argument for the loader-git worker.

    Args:
        batch_size (int): Not used

    Yields:
        expected dictionary of 'arguments' key

    """
    for line in sys.stdin:
        origin_url = line.rstrip()
        kwargs = {
            "url": origin_url,
            "lister_name": "github",
            "lister_instance_name": "github",
            "pack_size_bytes": 34359738368,
        }
        yield {
            "arguments": {
                "args": [],
                "kwargs": kwargs,
            },
        }


def stdin_to_git_normal_tasks(batch_size, type="git"):
    """Generates from stdin the proper task argument for the loader-git worker.

    Args:
        batch_size (int): Not used

    Yields:
        expected dictionary of 'arguments' key

    """
    for line in sys.stdin:
        origin_url = line.rstrip()
        kwargs = {
            "url": origin_url,
            "lister_name": "github",
            "lister_instance_name": "github",
        }
        yield {
            "arguments": {
                "args": [],
                "kwargs": kwargs,
            },
        }


def stdin_to_index_tasks(batch_size=1000):
    """Generates from stdin the proper task argument for the orchestrator.

    Args:
        batch_size (int): Number of sha1s to group together

    Yields:
        expected dictionary of 'arguments' key

    """
    try:
        from swh.indexer.producer import gen_sha1

        for sha1s in gen_sha1(batch=batch_size):
            yield {
                "arguments": {"args": [sha1s], "kwargs": {}},
            }
    except ImportError:
        pass


def print_last_hash(arguments: Dict) -> None:
    """Given a dict of arguments, take the sha1s list, print the last
    element as hex hash.

    """
    from swh.model.hashutil import hash_to_hex

    l = arguments["args"]
    if l:
        print(hash_to_hex(l[0][-1]))


QUEUES = {
    "svndump": {  # for svn, we use the same queue for length checking
        # and scheduling
        "task_name": "swh.loader.svn.tasks.MountAndLoadSvnRepository",
        "threshold": 1000,
        # to_task the function to use to transform the input in task
        "task_generator_fn": (lambda b: stdin_to_svn_tasks(b, type="dump")),
        "print_fn": print,
    },
    "svn": {  # for svn, we use the same queue for length checking
        # and scheduling
        "task_name": "swh.loader.svn.tasks.LoadSvnRepository",
        "threshold": 1000,
        # to_task the function to use to transform the input in task
        "task_generator_fn": stdin_to_svn_tasks,
        "print_fn": print,
    },
    "mercurial": {  # for mercurial, we use the same queue for length
        # checking and scheduling
        "task_name": "swh.loader.mercurial.tasks.LoadArchiveMercurial",
        "threshold": 1000,
        # to_task the function to use to transform the input in task
        "task_generator_fn": stdin_to_mercurial_tasks,
        "print_fn": print,
    },
    "bitbucket-mercurial": {
        "task_name": "oneshot:swh.loader.mercurial.tasks.LoadMercurial",
        "threshold": None,
        # to_task the function to use to transform the input in task
        "task_generator_fn": stdin_to_bitbucket_mercurial_tasks,
        "print_fn": print,
    },
    "indexer": {  # for indexer, we schedule using the orchestrator's queue
        # we check the length on the mimetype queue though
        "task_name": "swh.indexer.tasks.OrchestratorAllContents",
        "threshold": 1000,
        "task_generator_fn": stdin_to_index_tasks,
        "print_fn": print_last_hash,
    },
    "oneshot-large-git": {
        "task_name": "oneshot2:swh.loader.git.tasks.UpdateGitRepository",
        "threshold": 1000,
        # to_task the function to use to transform the input in task
        "task_generator_fn": stdin_to_git_large_tasks,
        "print_fn": print,
    },
    "oneshot-normal-git": {
        "task_name": "oneshot:swh.loader.git.tasks.UpdateGitRepository",
        "threshold": 1000,
        # to_task the function to use to transform the input in task
        "task_generator_fn": stdin_to_git_large_tasks,
        "print_fn": print,
    },
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
        queue_length = app.get_queue_length(app.tasks[queue_name].task_queue)
    except Exception:
        queue_length = None
    return queue_length


def send_new_tasks(app, queues_to_check):
    """Send new tasks for scheduling when possible. Check the queues_to_check's current
    number of scheduled tasks.

    If any of queues_to_check sees its threshold reached, we cannot
    send new tasks so this return False.  Otherwise, we can send new
    tasks so this returns True.

    Args:
        app: Application
        queues_to_check ([dict]): List of dict with keys 'task_name',
                                  'threshold'.

    Returns:
        True if we can send new tasks, False otherwise

    """
    for queue_to_check in queues_to_check:
        queue_name = queue_to_check["task_name"]
        threshold = queue_to_check["threshold"]

        _queue_length = queue_length_get(app, queue_name)
        if _queue_length is not None and _queue_length >= threshold:
            return False

    return True


@click.command(help="Read from stdin and send message to queue ")
@click.option("--queue-name", help="Queue concerned", type=click.Choice(QUEUES))
@click.option(
    "--threshold", help="Threshold for the queue", type=click.INT, default=1000
)
@click.option(
    "--batch-size",
    help="Batch size if batching is possible",
    type=click.INT,
    default=1000,
)
@click.option(
    "--waiting-time",
    help="Waiting time between checks",
    type=click.INT,
    default=MAX_WAITING_TIME,
)
def main(queue_name, threshold, batch_size, waiting_time, app=main_app):
    if queue_name not in QUEUES:
        raise ValueError("Unsupported %s, possible values: %s" % (queue_name, QUEUES))

    for module in app.conf.CELERY_IMPORTS:
        __import__(module)

    queue_information = QUEUES[queue_name]
    task_name = queue_information["task_name"]
    if ":" in task_name:
        task_name_without_prefix = task_name.split(":")[1]
    else:
        task_name_without_prefix = task_name

    if not threshold:
        threshold = queue_information["threshold"]

    # Retrieve the queues to check for current threshold limit reached
    # or not.  If none is provided (default case), we use the
    # scheduling queue as checking queue
    queues_to_check = queue_information.get(
        "queues_to_check",
        [
            {
                "task_name": task_name_without_prefix,
                "threshold": threshold,
            }
        ],
    )

    while True:
        throttled = False
        remains_data = False
        pending_tasks = []

        if send_new_tasks(app, queues_to_check):
            # we can send new tasks, compute how many we can send
            queue_length = queue_length_get(app, task_name_without_prefix)
            if queue_length is not None:
                nb_tasks_to_send = threshold - queue_length
            else:
                nb_tasks_to_send = threshold
        else:
            nb_tasks_to_send = 0

        if nb_tasks_to_send > 0:
            count = 0
            task_fn = queue_information["task_generator_fn"]
            for _task in task_fn(batch_size):
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

            print_fn = queue_information.get("print_fn", print)
            from kombu.utils.uuid import uuid

            for _task in pending_tasks:
                app.send_task(
                    task_name_without_prefix,
                    task_id=uuid(),
                    args=_task["arguments"]["args"],
                    kwargs=_task["arguments"]["kwargs"],
                    queue=task_name,
                )
                print_fn(_task["arguments"])

        else:
            throttled = True

        if throttled:
            time.sleep(waiting_time)


if __name__ == "__main__":
    main()
