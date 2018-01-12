#!/usr/bin/env python3

# Copyright (C) 2017-2018  The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information


import click
import sys
import time

from swh.model.hashutil import hash_to_hex

try:
    from swh.indexer.producer import gen_sha1
except ImportError:
    pass

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
        values = line.split(' ')
        origin_url = values[0]
        archive_path = values[1]
        visit_date = 'Tue, 3 May 2016 17:16:32 +0200'
        yield {
            'arguments': {
                'args': [origin_url, archive_path, visit_date],
                'kwargs': {},
             },
        }


def stdin_to_svn_tasks(batch_size):
    """Generates from stdin the proper task argument for the loader-svn
       worker.

    Args:
        batch_size (int): Not used

    Yields:
        expected dictionary of 'arguments' key

    """
    for line in sys.stdin:
        line = line.rstrip()
        values = line.split(' ')
        origin = values[0]
        path = values[1]
        visit_date = 'Tue, 3 May 2016 17:16:32 +0200'
        yield {
            'arguments': {
                'args': [path, origin, visit_date],
                'kwargs': {
                    'start_from_scratch': True,
                }
            },
        }


def stdin_to_index_tasks(batch_size=1000):
    """Generates from stdin the proper task argument for the orchestrator.

    Args:
        batch_size (int): Number of sha1s to group together

    Yields:
        expected dictionary of 'arguments' key

    """
    for sha1s in gen_sha1(batch=batch_size):
        yield {
            'arguments': {
                'args': [sha1s],
                'kwargs': {}
            },
        }


def print_last_hash(d):
    """Given a dict of arguments, take the sha1s list, print the last
       element as hex hash.

    """
    l = d['args']
    if l:
        print(hash_to_hex(l[0][-1]))


QUEUES = {
    'svndump': {  # for svn, we use the same queue for length checking
                  # and scheduling
        'task_name': 'swh.loader.svn.tasks.MountAndLoadSvnRepositoryTsk',
        'threshold': 1000,
        # to_task the function to use to transform the input in task
        'task_generator_fn': stdin_to_svn_tasks,
        'print_fn': print,
    },
    'mercurial': {  # for mercurial, we use the same queue for length
                    # checking and scheduling
        'task_name': 'swh.loader.mercurial.tasks.LoadArchiveMercurialTsk',
        'threshold': 1000,
        # to_task the function to use to transform the input in task
        'task_generator_fn': stdin_to_mercurial_tasks,
        'print_fn': print,
    },
    'indexer': {  # for indexer, we schedule using the orchestrator's queue
                  # we check the length on the mimetype queue though
        'task_name': 'swh.indexer.tasks.SWHOrchestratorAllContentsTask',
        'threshold': 1000,
        'queues_to_check': [{
                'task_name': 'swh.indexer.tasks.SWHContentMimetypeTask',
                'threshold': 1000,
            }, {
                'task_name': 'swh.indexer.tasks.SWHContentFossologyLicenseTask',  # noqa
                'threshold': 200,
            }
        ],
        'task_generator_fn': stdin_to_index_tasks,
        'print_fn': print_last_hash,
    }
}


def queue_length_get(app, queue_name):
    """Read the queue's current length.

    Args:
        app: Application
        queue_name: fqdn queue name to retrieve queue length from

    Returns:
        queue_name's length

    """
    return app.get_queue_length(app.tasks[queue_name].task_queue)


def send_new_tasks(app, queues_to_check):
    """Can we send new tasks for scheduling?  To answer this, we check the
    queues_to_check's current number of scheduled tasks.

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
        queue_name = queue_to_check['task_name']
        threshold = queue_to_check['threshold']

        _queue_length = queue_length_get(app, queue_name)
        if _queue_length >= threshold:
            return False

    return True


@click.command(help='Read from stdin and send message to queue ')
@click.option('--queue-name', help='Queue concerned')
@click.option('--threshold', help='Threshold for the queue',
              type=click.INT,
              default=None)
@click.option('--batch-size', help='Batch size if batching is possible',
              type=click.INT,
              default=1000)
@click.option('--waiting-time', help='Waiting time between checks',
              type=click.INT,
              default=MAX_WAITING_TIME)
def main(queue_name, threshold, batch_size, waiting_time, app=main_app):
    if queue_name not in QUEUES:
        raise ValueError("Unsupported %s, possible values: %s" % (
            queue_name, QUEUES))

    for module in app.conf.CELERY_IMPORTS:
        __import__(module)

    queue_information = QUEUES[queue_name]
    task_name = queue_information['task_name']
    scheduling_task = app.tasks[task_name]

    if not threshold:
        threshold = queue_information['threshold']

    # Retrieve the queues to check for current threshold limit reached
    # or not.  If none is provided (default case), we use the
    # scheduling queue as checking queue
    queues_to_check = queue_information.get('queues_to_check', [task_name])

    while True:
        throttled = False
        remains_data = False
        pending_tasks = []

        if send_new_tasks(app, queues_to_check):
            # we can send new tasks, compute how many we can send
            queue_length = queue_length_get(app, task_name)
            nb_tasks_to_send = threshold - queue_length
        else:
            nb_tasks_to_send = 0

        if nb_tasks_to_send > 0:
            count = 0
            task_fn = queue_information['task_generator_fn']
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

            print_fn = queue_information.get('print_fn', print)
            for _task in pending_tasks:
                args = _task['arguments']['args']
                kwargs = _task['arguments']['kwargs']
                scheduling_task.delay(*args, **kwargs)
                print_fn(_task['arguments'])

        else:
            throttled = True

        if throttled:
            time.sleep(waiting_time)


if __name__ == '__main__':
    main()
