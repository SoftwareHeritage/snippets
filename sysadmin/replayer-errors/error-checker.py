import redis
from swh.web.client.client import WebAPIClient
from swh.journal.serializers import kafka_to_value
from swh.model.model import Directory, Snapshot, Release, Revision
from swh.model.swhids import ObjectType
from swh.model import hashutil

## Scan the reported replayers errors and redistribute the entries
## in different databases according the type of error:
# Invalid Hash => db 4
# Content in kafka but not in storage => db 3
# Content in kafka, in storage and valid hash => db 2 These are real errors
#

API_URL = "https://webapp.staging.swh.network/api/1"
API_TOKEN = None

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

cli = WebAPIClient(api_url=API_URL, bearer_token=API_TOKEN)

# found_db = redis.Redis(db=FOUND_DB)
# not_found_db = redis.Redis(db=NOT_FOUND_DB)
# wrong_hash_db = redis.Redis(db=WRONG_HASH_DB)

reported = redis.Redis(db=REPORTER_DB, decode_responses=True)
raw_reported = redis.Redis(db=REPORTER_DB, decode_responses=False)

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

    print(f"cursor={cursor} keys={len(keys)}")

    pos += len(keys)
    checked = cli.known(keys)

    # breakpoint()
    print(f"storage reply received, checking the entries")

    for swhid in checked:
        total += 1
        known = checked.get(swhid)

        key = str(swhid)
        v = raw_reported.get(key)

        if known["known"]:
            found += 1

            object_as_dict = kafka_to_value(v)
            model_converter = None
            object_as_model = None

            if (swhid.object_type == ObjectType.DIRECTORY):
                model_converter = Directory
            elif (swhid.object_type == ObjectType.SNAPSHOT):
                model_converter = Snapshot
            elif (swhid.object_type == ObjectType.RELEASE):
                model_converter = Release
            elif (swhid.object_type == ObjectType.REVISION  ):
                model_converter = Revision
            else:
                print(f"unsupported {swhid}")

            if model_converter:
                object_as_model = model_converter.from_dict(object_as_dict)

                computed_hash = object_as_model.compute_hash()

                computed_hash_str = hashutil.hash_to_hex(computed_hash)
                computed_id = hashutil.hash_to_hex(object_as_model.id)

                if computed_hash != object_as_model.id:
                    wrong_hash += 1
                    # print(f"{key}: wrong hash computed_hash:{computed_hash_str}")
                    # breakpoint()
                    reported.move(key, WRONG_HASH_DB)
                    # wrong_hash_db.set(key, v)
                    # reported.delete(key)


        else:
            not_found += 1
            if v is None:
                raise Exception(f"{key} not found")
            reported.move(key, NOT_FOUND_DB)
            # not_found_db.add(key, v)
            # reported_db.delete(key)

    print(f"checked={total} found={found} not_found={not_found} wrong_hash={wrong_hash}")

    if cursor == 0:
        break

