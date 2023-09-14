import redis
from swh.web.client.client import WebAPIClient
from swh.journal.serializers import kafka_to_value
from swh.model.model import Directory, Snapshot, Release, Revision
from swh.model.swhids import ObjectType
from swh.model import hashutil

# swh-storage batch size
BATCH_SIZE = 10

REPORTER_DB = 1


reported = redis.Redis(db=REPORTER_DB, decode_responses=True)
cursor = 0
pos = 0

total = 0
found = 0
not_found = 0
wrong_hash = 0

while True:
    result = reported.scan(cursor=cursor, count=BATCH_SIZE)

    cursor = result[0]
    keys = result[1]

    # print(f"cursor={cursor} keys={len(keys)}")

    pos += len(keys)
    # print(f"keys: {keys}")

    for key in keys:
        if key.startswith("directory:"):
            hash = key.split(":")[1]
            new_id = f"swh:1:dir:{hash}"
            print(f"Renaming {key} to {new_id}")
            reported.rename(key, new_id)

    if cursor == 0:
        break


