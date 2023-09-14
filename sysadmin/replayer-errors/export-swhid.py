import redis
from swh.web.client.client import WebAPIClient
from swh.journal.serializers import kafka_to_value
from swh.model.model import Directory, Snapshot, Release, Revision
from swh.model.swhids import CoreSWHID, ObjectType
from swh.model import hashutil

## Scan the reported replayers errors and export the swhid in
## several files:
# - 'unchecked.lst': the errors found by the replayers but not verified
# - 'errors.lst': True errors, something wrong happened during the replay
# - 'kafka-noise.lst': Object in kafka but not in the backed
# - 'wrong-hash.lst': Objects having a wrong hash

# swh-storage batch size
BATCH_SIZE = 1000

REPORTER_DB = 1
# the DB for the swhids found in the original storage
# It can be considered as real errors
FOUND_DB = 2
# the DB for the swhids not found in the origin storage
# It's probably noise in kafka
NOT_FOUND_DB = 3
# The DB for the objects with a wrong recomputed hash
WRONG_HASH_DB = 4
# The DB for the objects with a unserialization error detected
ERROR_DB = 9

# found_db = redis.Redis(db=FOUND_DB)
# not_found_db = redis.Redis(db=NOT_FOUND_DB)
# wrong_hash_db = redis.Redis(db=WRONG_HASH_DB)

reported_db = redis.Redis(db=REPORTER_DB, decode_responses=True)
found_db = redis.Redis(db=FOUND_DB, decode_responses=True)
kafka_noise_db = redis.Redis(db=NOT_FOUND_DB, decode_responses=True)
wrong_hash_db = redis.Redis(db=WRONG_HASH_DB, decode_responses=True)
error_db = redis.Redis(db=ERROR_DB, decode_responses=True)

cursor = 0
pos = 0

total = 0
not_found = 0
wrong_hash = 0
errors = 0

def export_db_content(filename, redis_db, compute_hash=False):
    pos=0

    decoded_db = redis.Redis(db=redis_db, decode_responses=True)
    raw_db = redis.Redis(db=redis_db, decode_responses=False)

    f = open(filename, "w")
    cursor = 0

    while True:
        result = decoded_db.scan(cursor=cursor, count=BATCH_SIZE)

        cursor = result[0]
        keys = result[1]

        print(f"filename={filename} cursor={cursor} keys={len(keys)} compute_hash={compute_hash}")

        pos += len(keys)

        for key in keys:
            f.write(f"{key}")

            if compute_hash:
                v = raw_db.get(key)
                object_as_dict = kafka_to_value(v)
                model_converter = None
                object_as_model = None

                swhid = CoreSWHID.from_string(key)

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
                    try:
                        object_as_model = model_converter.from_dict(object_as_dict)
                    except Exception as e:
                        print(f"Error deserializing {key}: {e}")
                        continue

                    computed_hash = object_as_model.compute_hash()
                    computed_hash_str = hashutil.hash_to_hex(computed_hash)

                    f.write(f";{computed_hash_str}")

            f.write("\n")

        if cursor == 0:
            break

# export_db_content('unchecked.lst', REPORTER_DB)
# export_db_content('errors.lst', FOUND_DB)
# export_db_content('kafka-noise.lst', NOT_FOUND_DB)
export_db_content('wrong-hash.lst', WRONG_HASH_DB, compute_hash=True)
# export_db_content('serialization_errors.lst', ERROR_DB)
