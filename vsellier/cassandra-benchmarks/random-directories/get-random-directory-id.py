from swh.storage import get_storage
from swh.model.hashutil import hash_to_bytes
import sys

COUNT=100000

config = {"url": "http://storage-cassandra.internal.staging.swh.network"}
# config = {"url": "http://webapp.internal.staging.swh.network:5002"}
# config = {"url": "http://localhost:5002"}

storage = get_storage("remote", **config)

# print(get_storage('remote', url='http://swh-storage:5002/').directory_get_random().hex())"; done > directory_1000-3.lst

storage.check_config(check_write=False)

for i in range(COUNT):
    if i%100 == 0:
        print(f"{i}", file=sys.stderr)
    print(storage.directory_get_random().hex())
