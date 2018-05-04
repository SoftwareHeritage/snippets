#!/usr/bin/env python3

import tqdm
import collections
import logging
from time import sleep
from datetime import datetime
from pathlib import Path
from pony.orm import Database, Required, Optional, select, db_session, commit
from swh.vault.api.client import RemoteVaultClient


ORIGINS_PATH = Path('/home/seirl/crossminer_origins')
SQLITE_PATH = '/home/seirl/crossminer_origins_db.sqlite'
VAULT_URL = 'http://orangerie.internal.softwareheritage.org:5005/'
# VAULT_URL = 'http://localhost:5005/'

db = Database()
client = RemoteVaultClient(VAULT_URL)


class Batch(db.Entity):
    filename = Required(str)
    vault_id = Optional(int)
    ts_start = Optional(datetime, default=datetime.utcnow)
    ts_done = Optional(datetime)

    def full_path(self):
        return ORIGINS_PATH / self.filename

    def origins(self):
        with self.full_path().open() as f:
            for l in f:
                hash, origin = list(l.split())
                yield hash, origin

    def batch_query(self):
        return list(dict.fromkeys(
            [('directory', hash) for hash, origin in self.origins()]))

    def send(self):
        query = self.batch_query()
        res = client.batch_cook(query)
        self.vault_id = res['id']
        logging.info('Sent batch %s, size %s, vault_id %s',
                     self.filename, len(query), self.vault_id)

    def update_progress(self):
        res = client.batch_progress(self.vault_id)
        if res is None:
            logging.warning("Remote Vault batch %s returned 404.",
                            self.vault_id)
        logging.debug('Batch %s: %d new, %d pending, %d failed, %d done '
                      '/ %d total', self.vault_id, res['new'], res['pending'],
                      res['failed'], res['done'], res['total'])
        if res['new'] == 0 and res['pending'] == 0:
            self.ts_done = datetime.utcnow()
        return res

    @classmethod
    @db_session
    def empty(cls):
        return not select(b for b in cls).count()


@db_session
def load_batches():
    for batch_fname in sorted(ORIGINS_PATH.glob('*.csv')):
        logging.info('Loading batch %s', batch_fname.name)
        Batch(filename=batch_fname.name)


def get_current_batch():
    b = (select(b for b in Batch if b.ts_done is None).order_by(Batch.id))
    if b is None:
        return None
    return b.first()


@db_session
def careful_main_loop():
    while True:
        b = get_current_batch()
        if b is None:
            break
        if b.vault_id is None:
            b.send()
        else:
            b.update_progress()

        sleep(5)


@db_session
def send_all_batches_directly():
    for b in select(b for b in Batch if b.vault_id is None):
        b.send()
        commit()


@db_session
def check_progress_loop():
    pbar = None
    while True:
        c = collections.Counter()
        for b in select(b for b in Batch if b.vault_id is not None):
            res = b.update_progress()
            statuses = ('new', 'pending', 'failed', 'done', 'total')
            c += collections.Counter({k: res[k] for k in statuses if k in res})

        done = c['done'] + c['failed']
        if pbar is None:
            pbar = tqdm.tqdm(initial=done, total=c['total'])
        else:
            delta = done - pbar.n
            # Sometimes, tasks can go pending after being done because they got
            # scheduled twice (shouldn't happen, but *someone* (kof kof) did a
            # delete on the database with a heavy hand), but tqdm can't go
            # backwards, so we only update it if the delta is positive.
            if delta >= 0:
                pbar.update(done - pbar.n)
        if done == c['total']:
            break
        sleep(5)
    pbar.close()


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    db.bind(provider='sqlite', filename=SQLITE_PATH, create_db=True)
    db.generate_mapping(create_tables=True)
    if Batch.empty():
        load_batches()
    send_all_batches_directly()
    check_progress_loop()
