import redis
from swh.web.client.client import WebAPIClient
from swh.journal.serializers import kafka_to_value
from swh.model.model import Directory, Snapshot, Release, Revision
from swh.model.swhids import ObjectType
from swh.model import hashutil

## Scan the reported replayers errors and export the swhid in
## several files:
- 'unchecked.lst': the errors found by the replayers but not verified
- 'errors.lst': True errors, something wrong happened during the replay
- 'kafka-noise.lst': Object in kafka but not in the backed
- 'wrong-hash.lst': Objects having a wrong hash

# swh-storage batch size
BATCH_SIZE = 100

REPORTER_DB = 1
# the DB for the swhids found in the original storage
# It can be considered as real errors
FOUND_DB = 2
# the DB for the swhids not found in the origin storage
# It's probably noise in kafka
NOT_FOUND_DB = 3
# The DB for the objects with a wrong recomputed hash
WRONG_HASH_DB = 4

# found_db = redis.Redis(db=FOUND_DB)
# not_found_db = redis.Redis(db=NOT_FOUND_DB)
# wrong_hash_db = redis.Redis(db=WRONG_HASH_DB)

reported = redis.Redis(db=REPORTER_DB, decode_responses=True)
found = redis.Redis(db=FOUND_DB, decode_responses=True)
kafka_noise = redis.Redis(db=NOT_FOUND_DB, decode_responses=True)
wrong_hash = redis.Redis(db=WRONG_HASH_DB, decode_responses=True)

cursor = 0
pos = 0

total = 0
found = 0
not_found = 0
wrong_hash = 0


def export_db_content(filename, redis_db):
    pos=0

    f = open(filename, "a")
    cursor = 0

    while True:
        result = redis_db.scan(cursor=cursor, count=BATCH_SIZE)

        cursor = result[0]
        keys = result[1]

        print(f"filename={filename} cursor={cursor} keys={len(keys)}")

        pos += len(keys)

        for key in keys:
            f.write(f"{key}\n")

        if cursor == 0:
            break



export_db_content('unchecked.lst', reported)
export_db_content('errors.lst', found)
export_db_content('kafka-noise.lst', kafka_noise)
export_db_content('wrong-hash.lst', wrong_hash)

