import redis
from swh.storage import get_storage
from swh.journal.serializers import kafka_to_value
from swh.model.model import Directory, Snapshot, Release, Revision
from swh.model.swhids import CoreSWHID, ObjectType
from swh.model import hashutil

## Scan the reported replayers errors and redistribute the entries
## in different databases according the type of error:
# Invalid Hash => db 4
# Content in kafka, in storage and valid hash => db 2 These are real errors
#

# Try to replay errors checked by errors-checker.py
# For content in kafka, in storage and valid hash (db2)
# - if add is ok -> move the key to db5
# - if add is ko -> move the key to db6
#
# For invalid hash (db4):
# - if add is ok -> move the key to db7
# - if add is ko -> move the key to db8


# Port forward from the cluster
CASSANDRA_STORAGE_URL = 'http://localhost:5002'

storage_configuration = {"url": CASSANDRA_STORAGE_URL}

storage = get_storage("remote", **storage_configuration)

storage.check_config(check_write=True)
print("connected to swh-storage")

# Staging
#API_URL = "https://webapp.staging.swh.network/api/1"
#API_TOKEN = '[redacted]'

# Production
# API_URL = "https://archive.softwareheritage.org/api/1"
# API_TOKEN = '[redacted]'

# swh-storage batch size
BATCH_SIZE = 100

# the DB for the swhids found in the original storage
# It can be considered as real errors
FOUND_DB = 2
FOUND_DB_ADD_OK=5
FOUND_DB_ADD_KO=6
FOUND_DB_ADD_NEW=9
# The DB for the objects with a wrong recomputed hash
WRONG_HASH_DB = 4
WRONG_HASH_DB_ADD_OK=7
WRONG_HASH_DB_ADD_KO=8
WRONG_HASH_DB_ADD_NEW=10


def replay_db_content(db_source, db_ok, db_ko, db_new, move_source = False):
    cursor = 0
    pos = 0

    total = 0
    replayed = 0
    error = 0
    added = 0
    unsupported = 0

    source_db = redis.Redis(db=db_source, decode_responses=True)
    source_db_raw = redis.Redis(db=db_source, decode_responses=False)
    new_db = redis.Redis(db=db_new)

    while True:
        result = source_db.scan(cursor=cursor, count=BATCH_SIZE)

        cursor = result[0]
        keys = result[1]

        print(f"cursor={cursor} keys={len(keys)}")

        pos += len(keys)

        for swhid_b in keys:

            swhid_str = str(swhid_b)
            swhid = CoreSWHID.from_string(swhid_str)

            total += 1

            model_converter = None
            add_function = None
            object_as_model = None

            if (swhid.object_type == ObjectType.DIRECTORY):
                model_converter = Directory
                add_function = storage.directory_add
            elif (swhid.object_type == ObjectType.SNAPSHOT):
                model_converter = Snapshot
                add_function = storage.snapshot_add
            elif (swhid.object_type == ObjectType.RELEASE):
                model_converter = Release
                add_function = storage.release_add
            elif (swhid.object_type == ObjectType.REVISION  ):
                model_converter = Revision
                add_function = storage.revision_add
            else:
                print(f"unsupported {swhid}")
                unsupported += 1
                continue

            # breakpoint()
            v = source_db_raw.get(swhid_str)
            object_as_dict = kafka_to_value(v)

            object_as_model = model_converter.from_dict(object_as_dict)
            res = add_function([object_as_model])
            replayed += 1
            count = list(res.values())[0]
            new = count > 0
            added += count

            if new:
                new_db.set(swhid_str, v)

            if move_source:
                source_db.move(swhid_str, db_ok)

        print(f"objects={total} unsupported={unsupported} replayed={replayed} added={added}")

        if cursor == 0:
            break

        # breakpoint()
    print(f"final for db{db_source}: objects={total} unsupported={unsupported} replayed={replayed} added={added}")

replay_db_content(FOUND_DB, FOUND_DB_ADD_OK, FOUND_DB_ADD_KO, FOUND_DB_ADD_NEW, move_source=True)
replay_db_content(WRONG_HASH_DB, WRONG_HASH_DB_ADD_OK, WRONG_HASH_DB_ADD_KO, WRONG_HASH_DB_ADD_NEW, move_source=True)
