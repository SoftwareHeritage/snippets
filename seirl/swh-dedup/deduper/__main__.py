import logging
import sys
from multiprocessing import Process, Queue
from swh.model.hashutil import hash_to_bytes
from swh.objstorage.exc import ObjNotFoundError

from deduper.deduper import Deduper


NUM_WORKERS = 1


def dedup_worker(task_queue, result_queue):
    while True:
        content_id = task_queue.get()
        if content_id is None:  # no more tasks
            break

        try:
            Deduper().dedup(hash_to_bytes(content_id))
            result_queue.put((content_id, True))
        except ObjNotFoundError:
            logging.warning('cannot find object "%s", skipping' % content_id)
            result_queue.put((content_id, False))


def progress_monitor(result_queue):
    obj_count = 0
    while True:
        (content_id, _success) = result_queue.get()
        obj_count += 1
        if obj_count % 1000 == 0:
            logging.info('processed %d objects, currently at %s' %
                         (obj_count, content_id))


def main():
    task_queue = Queue()
    result_queue = Queue()

    workers = []
    for i in range(0, NUM_WORKERS):
        p = Process(target=dedup_worker,
                    args=(task_queue, result_queue))
        workers.append(p)
        p.start()

    monitor = Process(target=progress_monitor, args=(result_queue,))
    monitor.start()

    for line in sys.stdin:  # schedule tasks
        content_id = line.rstrip()
        task_queue.put(content_id)
    for i in range(0, NUM_WORKERS):  # tell workers we're done
        task_queue.put(None)

    for p in workers:  # wait for completion
        p.join()
    monitor.terminate()


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    main()
