#!/usr/bin/env python3

# Copyright (C) 2017  The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information


import click
import sys
import time

from swh.scheduler.celery_backend.config import app as main_app


# Max batch size for tasks
MAX_NUM_TASKS = 10000


QUEUES = {
    'svndump': 'swh.loader.svn.tasks.MountAndLoadSvnRepositoryTsk',
}


@click.command(help='Read from stdin and send message to queue ')
@click.option('--queue-name', help='Queue concerned')
@click.option('--threshold', help='Threshold for the queue',
              default=MAX_NUM_TASKS)
def main(queue_name, threshold, app=main_app):
    if queue_name not in QUEUES:
        raise ValueError("Unsupported %s, possible values: %s" % (
            queue_name, QUEUES))

    for module in app.conf.CELERY_IMPORTS:
        __import__(module)

    task_name = QUEUES[queue_name]
    task = app.tasks[task_name]
    print(task)
    queue_name = task.task_queue

    while True:
        throttled = False
        remains_data = False
        pending_tasks = []

        queue_length = app.get_queue_length(queue_name)
        print('##### queue name: %s' % queue_name)
        print('##### threshold: %s' % threshold)
        print('##### queue length: %s' % queue_length)

        if queue_length < threshold:
            nb_tasks_to_send = threshold - queue_length
        else:     # queue_length >= threshold
            nb_tasks_to_send = 0
            throttled = True

        print('##### nb tasks to send: %s' % nb_tasks_to_send)

        if nb_tasks_to_send > 0:
            print('##### %s to send' % nb_tasks_to_send)
            count = 0
            for line in sys.stdin:
                line = line.rstrip()
                values = line.split(' ')
                origin = values[0]
                path = values[1]

                visit_date = 'Tue, 3 May 2016 17:16:32 +0200'

                _task = {
                    'arguments': {
                        'args': [path, origin, visit_date],
                        'kwargs': {
                            'start_from_scratch': True,
                        }
                    },
                }
                print(_task)
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

            for _task in pending_tasks:
                args = _task['arguments']['args']
                kwargs = _task['arguments']['kwargs']

                task.delay(*args, **kwargs)

        if throttled:
            time.sleep(10)


if __name__ == '__main__':
    main()
