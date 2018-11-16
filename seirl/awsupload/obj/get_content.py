#!/usr/bin/env python3

import json
import queue
import subprocess
import sys
import tempfile
import threading
import time
import tqdm


AZURE_KEYS = ([  # noqa
    ('0euwestswh', '?st=2000-01-01T00%3A00%3A00Z&se=2100-01-01T00%3A00%3A00Z&sp=rl&spr=https&sv=2017-04-17&ss=b&srt=sco&sig=L%2BjRetar9wFeg/QG4sTJQzGIiJ0PbdKet0WQ0bp7x10%3D'),
    ('1euwestswh', '?st=2000-01-01T00%3A00%3A00Z&se=2100-01-01T00%3A00%3A00Z&sp=rl&spr=https&sv=2017-04-17&ss=b&srt=sco&sig=DkjhDjP6mn4pMXmZgWoQ44YZuv8Y6jbBkWnlhTwdze4%3D'),
    ('2euwestswh', '?st=2000-01-01T00%3A00%3A00Z&se=2100-01-01T00%3A00%3A00Z&sp=rl&spr=https&sv=2017-04-17&ss=b&srt=sco&sig=Ci3vdy4rdu7ti0Z06lTVYZzexuRfQgc01SOc3X/EqDs%3D'),
    ('3euwestswh', '?st=2000-01-01T00%3A00%3A00Z&se=2100-01-01T00%3A00%3A00Z&sp=rl&spr=https&sv=2017-04-17&ss=b&srt=sco&sig=xMR1AQbshcaNCwZ7xDVRG%2BO6gGKjP4i9H4w5TCAY7tg%3D'),
    ('4euwestswh', '?st=2000-01-01T00%3A00%3A00Z&se=2100-01-01T00%3A00%3A00Z&sp=rl&spr=https&sv=2017-04-17&ss=b&srt=sco&sig=rWPTHnnIopkRu0qdhY%2BSoaW0fcFzCNvPHOuSjrLyPj0%3D'),
    ('5euwestswh', '?st=2000-01-01T00%3A00%3A00Z&se=2100-01-01T00%3A00%3A00Z&sp=rl&spr=https&sv=2017-04-17&ss=b&srt=sco&sig=l4qrI4YGKBKOKHcK6W%2BKTPotiLZBXYf0H8d6jR7eyHo%3D'),
    ('6euwestswh', '?st=2000-01-01T00%3A00%3A00Z&se=2100-01-01T00%3A00%3A00Z&sp=rl&spr=https&sv=2017-04-17&ss=b&srt=sco&sig=vkQVTEmXcpAUR5hypYxv4iCvbijsI9yx00UJ4Bkst3c%3D'),
    ('7euwestswh', '?st=2000-01-01T00%3A00%3A00Z&se=2100-01-01T00%3A00%3A00Z&sp=rl&spr=https&sv=2017-04-17&ss=b&srt=sco&sig=D8Ym8wwRfSow1%2B24Tmrhy4v3I9Qyv4i08oEYRDivE34%3D'),
    ('8euwestswh', '?st=2000-01-01T00%3A00%3A00Z&se=2100-01-01T00%3A00%3A00Z&sp=rl&spr=https&sv=2017-04-17&ss=b&srt=sco&sig=vVcm%2BDgkRZv6ia/bjl4iLuPZ3YHvwKrABvALF3ld1K0%3D'),
    ('9euwestswh', '?st=2000-01-01T00%3A00%3A00Z&se=2100-01-01T00%3A00%3A00Z&sp=rl&spr=https&sv=2017-04-17&ss=b&srt=sco&sig=rwAvhMLrfOYCo84mEnaW4alJNSEDR3UNBVF0IgqWR%2Bg%3D'),
    ('aeuwestswh', '?st=2000-01-01T00%3A00%3A00Z&se=2100-01-01T00%3A00%3A00Z&sp=rl&spr=https&sv=2017-04-17&ss=b&srt=sco&sig=RikR/3nKmJ5xJUjaWv%2BI4GyzS7ZHm3VczOV9cQidKyA%3D'),
    ('beuwestswh', '?st=2000-01-01T00%3A00%3A00Z&se=2100-01-01T00%3A00%3A00Z&sp=rl&spr=https&sv=2017-04-17&ss=b&srt=sco&sig=q/OH1gcBDw7AGn8MOevNiHQ8UPwhlvsH7vagZA1uKHI%3D'),
    ('ceuwestswh', '?st=2000-01-01T00%3A00%3A00Z&se=2100-01-01T00%3A00%3A00Z&sp=rl&spr=https&sv=2017-04-17&ss=b&srt=sco&sig=4oXXqk7AgTRw9ELBBe4prIzP2hhEHw7uclik1yMJFwA%3D'),
    ('deuwestswh', '?st=2000-01-01T00%3A00%3A00Z&se=2100-01-01T00%3A00%3A00Z&sp=rl&spr=https&sv=2017-04-17&ss=b&srt=sco&sig=UI6cogo7XBYL%2BHIdRFgHZV0DdcIkuG3p/6bSmTk7M9A%3D'),
    ('eeuwestswh', '?st=2000-01-01T00%3A00%3A00Z&se=2100-01-01T00%3A00%3A00Z&sp=rl&spr=https&sv=2017-04-17&ss=b&srt=sco&sig=BgBkVfu77C4bu/per0tSBmQzNlo9f5l6ogjVIN5DT/Y%3D'),
    ('feuwestswh', '?st=2000-01-01T00%3A00%3A00Z&se=2100-01-01T00%3A00%3A00Z&sp=rl&spr=https&sv=2017-04-17&ss=b&srt=sco&sig=CwMbiqsm6M6R0zwnBNQLwBkxboUBihjJZv03LaHJTL4%3D'),
])

CONCURRENCY = 10
PREFIX_SIZE = 5
OBJS_ROOT = '/tmp/content-tmp'
RESUME_PATH = '/root/content-resume-prefix.json'


def prefix_yielder(start=0, end=0x10 ** PREFIX_SIZE):
    for i in range(start, end):
        yield '{num:0{w}x}'.format(num=i, w=PREFIX_SIZE)


class ResumableStateTracker:
    def __init__(self, iterator, path):
        self.path = path
        self.it = iterator

        self.old_task_set = set()
        self.task_set = set()
        self.last = None
        self.initial_skipped = 0

        self._load()

        # skip to current
        if self.last is not None:
            while True:
                self.initial_skipped += 1
                cur = next(self.it)
                if cur == self.last:
                    break

    def _load(self):
        try:
            with open(self.path) as f:
                saved = json.load(f)
        except OSError:
            return

        self.old_task_set = set(saved['task_set'])
        self.last = saved['last']

    def save(self):
        d = {'task_set': list(self.old_task_set | self.task_set),
             'last': self.last}
        with open(self.path, 'w') as f:
            json.dump(d, f)

    def acquire_item(self):
        if self.old_task_set:
            item = sorted(self.old_task_set)[0]
            self.old_task_set.remove(item)
        else:
            item = next(self.it)
            self.last = item

        self.task_set.add(item)
        self.save()
        return item

    def done(self, item):
        try:
            self.task_set.remove(item)
        except KeyError:
            tqdm.tqdm.write('{}: warning: did the same task twice'
                            .format(item))
        self.save()


def upload_prefix(prefix):
    shard, key = AZURE_KEYS[int(prefix[0], 16)]
    url = 'https://{}.blob.core.windows.net/contents'.format(shard)
    with tempfile.TemporaryDirectory(prefix='swh-s3loader-',
                                     dir=OBJS_ROOT) as objs_dir:
        tqdm.tqdm.write('{}: downloading'.format(prefix))
        with tempfile.TemporaryDirectory(prefix='swh-azresume-') as resdir:
            subprocess.run(
                [
                    'azcopy',
                    '--quiet',
                    '--source', url,
                    '--source-sas', key,
                    '--destination', objs_dir,
                    '--include', prefix,
                    '--resume', resdir,
                    '--recursive'
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )

        tqdm.tqdm.write('{}: uploading'.format(prefix))
        subprocess.run(
            [
                'aws', 's3', 'cp',
                '--recursive',
                '--quiet',
                # '--region', 'eu-west-2',
                objs_dir,
                's3://softwareheritage/content/'
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        '''
        subprocess.run(
            [
                '/root/parquet/.venv/bin/python', '/root/s3upload.py',
                # '--region', 'eu-west-2',
                objs_dir,
                'content-test'
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        '''

    tqdm.tqdm.write('{}: done'.format(prefix))


def worker(q, tracker, pbar):
    while True:
        item = q.get()
        if item is None:
            break

        # No max retries, we want manual intervention in case of error
        while True:
            try:
                upload_prefix(item)
            except Exception as e:
                tqdm.tqdm.write('{}: "{}", retrying in 10sec'
                                .format(item, str(e)))
                time.sleep(10)
            else:
                break
        tracker.done(item)
        q.task_done()
        pbar.update(1)


def scheduler(iterator):
    tracker = ResumableStateTracker(iterator, RESUME_PATH)
    q = queue.Queue(maxsize=1)
    threads = []
    initial = tracker.initial_skipped - len(tracker.old_task_set)
    pbar = tqdm.tqdm(initial=initial, total=16 ** PREFIX_SIZE)
    for i in range(CONCURRENCY):
        t = threading.Thread(target=worker, args=(q, tracker, pbar),
                             daemon=True)
        t.start()
        threads.append(t)

    with pbar:
        while True:
            try:
                item = tracker.acquire_item()
            except StopIteration:
                break
            q.put(item)

    q.join()
    for t in threads:
        q.put(None)
    for t in threads:
        t.join()


def main():
    if len(sys.argv) >= 3:
        start = int(sys.argv[1], 16)
        end = int(sys.argv[1], 16) + 1
        iterator = iter(prefix_yielder(start, end))
    else:
        iterator = iter(prefix_yielder())
    scheduler(iterator)


if __name__ == '__main__':
    main()
