#!/usr/bin/env python3

from pony.orm import select, db_session

from send_batches import load, Batch


@db_session
def get_batches():
    done = []
    batches = select(batch for batch in Batch)
    for b in batches:
        p = b.update_progress()
        for bundle in p['bundles']:
            if bundle['status'] == 'done':
                done.append(bundle['obj_id'])
    if len(done) >= 30000:
        print('\n'.join(done))
        return


if __name__ == '__main__':
    load()
    get_batches()
