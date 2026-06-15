#!/usr/bin/env python
# coding: utf-8
"""Use with a CSV file exported from athena with such a query:

```
SELECT sha1,
        sha256,
        length
FROM content
where length <= 95000000 and length > 90000000
order by length desc
```

and a SWH_CONFIG_FILENAME yaml file with a toplevel list of objstorage
definitions, each with a name.

CSV split:

```
filename=/srv/storage/space/personal/olasd/largest_contents_60M.csv
num_files=10
seq_max=$((num_files - 1))
count=$(($(wc -l $filename | awk '{print $1}') / num_files + 1))
for i in `seq 0 $seq_max`; do
    offset=$((2 + count*i))
    (head -1 $filename; tail -n +$offset $filename | head -$count) >$(basename $filename .csv)_split$i.csv
done
```
"""

import csv
import enum
import logging
import os
import sys

import yaml

from swh.objstorage.factory import get_objstorage

logger = logging.getLogger("__main__")

DO_REMOVAL = True


class RemovalState(enum.Enum):
    NotInLocal = 0
    DeleteOK = 1
    DeleteNotOK = 2


def get_objstorages_from_config():
    config = yaml.safe_load(open(os.environ["SWH_CONFIG_FILENAME"], "r"))
    print(config)
    return {args["name"]: get_objstorage(**args) for args in config["objstorages"]}


def check_objstorages(
    local_objstorage, other_objstorages, obj_id
) -> (RemovalState, list[str]):
    if obj_id not in local_objstorage:
        return RemovalState.NotInLocal, []

    missing = []
    for objstorage in other_objstorages:
        if obj_id not in objstorage:
            missing.append(objstorage.name)

    if not missing:
        return RemovalState.DeleteOK, []
    else:
        return RemovalState.DeleteNotOK, missing


def delete_in_objstorage(local_objstorage, obj_id) -> int:
    if DO_REMOVAL:
        local_objstorage.delete(obj_id)
    logger.debug("Removed %s, size %s", obj_id["sha256"].hex(), obj_id["length"])
    return obj_id["length"]


if __name__ == "__main__":
    csv_filename = sys.argv[1]
    delete_objstorage = sys.argv[2]
    objstorages = get_objstorages_from_config()
    local_objstorage = objstorages[delete_objstorage]
    other_objstorages = [objstorages[k] for k in objstorages if k != delete_objstorage]

    logging.basicConfig(level=logging.INFO)
    logger.setLevel(logging.INFO)
    logging.getLogger("azure").setLevel(logging.CRITICAL)

    deleted_bytes = 0
    deleted_objects = 0
    notlocal_objects = 0
    notok_objects = 0
    total_objects = 0

    for line in csv.DictReader(open(csv_filename)):
        obj_id = {
            k: bytes.fromhex(v) if k.startswith("sha") else int(v)
            for k, v in line.items()
        }

        total_objects += 1

        match check_objstorages(local_objstorage, other_objstorages, obj_id):
            case RemovalState.DeleteOK, []:
                deleted_bytes += delete_in_objstorage(local_objstorage, obj_id)
                deleted_objects += 1
            case RemovalState.NotInLocal, []:
                notlocal_objects += 1
            case RemovalState.DeleteNotOK, missing:
                logger.info(
                    "Could not remove sha1:%s,sha256:%s: missing from %s",
                    obj_id["sha1"].hex(),
                    obj_id["sha256"].hex(),
                    ", ".join(missing),
                )
                notok_objects += 1

        if total_objects % 100 == 0:
            logger.info(
                "Deleted: %s (bytes: %s), Not found locally: %s, Not removable: %s",
                deleted_objects,
                deleted_bytes,
                notlocal_objects,
                notok_objects,
            )
