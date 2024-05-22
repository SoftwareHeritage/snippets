#!/usr/bin/env python3
# vim: ai

from swh.model.model import *
from analyze_disk_representation import *
from get_journal_check_and_replay import *
from swh.storage.algos.directory import (
    directory_get_many_with_possibly_duplicated_entries,
)
import os
from pprint import pprint
from collections import OrderedDict


config_file = "/etc/swh/config.yml"
config = read_config(config_file)
cs_storage = get_storage("cassandra", **config["cassandra"])
pg_storage = get_storage("postgresql", **config["postgresql"])
dir_volume = "/volume/cassandra-checks-volume/to_replay/directory/"
counter = {
    # type and name ok but perms are different
    "perms_mismatched": 0,
    # name and perms ok but type is different
    "type_mismatched": 0,
    # name ok but type and perms are different
    "type_and_perms_mismatched": 0,
    # type ok but name and perms are different
    "name_and_perms_mismatched": 0,
    # type and name are different (perms ok)
    "type_and_name_mismatched": 0,
    # all type, name and perms are different
    "type_and_name_and_perms_mismatched": 0,
    # perms and type ok but name is different
    "name_mismatched": 0,
    # Check whether the list of directory entries are different between postgres and
    # cassandra
    "entries_number_mismatched": 0,
    # Objects multiple times replayed
    "cs_not_equals_pg": 0,
    # That number should stay at 0, otherwise, we miss an analysis
    "unknown": 0,
    # total of inconsistencies in the directory set (should be equal to the sum of the
    # other keys)
    "total_mismatched": 0,
    # missing in cassandra
    "missing": 0,
    # missing in cassandra and with corrupted hash
    "missing_corrupted_hash": 0,
    # total_missing in cassandra
    "total_missing": 0,
    # All problematic objects
    "total": 0,
}


def compare_swhid_in_cassandra(swhid_path):
    result = OrderedDict()
    jn_rep, cass_rep, pg_rep = from_path_to_rep(swhid_path)
    if jn_rep is None:  # Cannot compare anything if empty, return empty result
        return result
    _, _, _, cs_get, _ = configure_obj_get("directory", jn_rep, cs_storage, pg_storage)
    try:
        cs_dir = next(iter([o for o in cs_get() if o]))
    except:
        # directory was not read in cassandra, marked as missing too
        return result
    assert cs_dir.id == pg_rep.id
    assert cs_dir.id == jn_rep["id"]
    if cs_dir != pg_rep:
        sorted_cs_entries = sorted(cs_dir.entries)
        sorted_pg_entries = sorted(pg_rep.entries)

        if len(sorted_cs_entries) != len(sorted_pg_entries):
            result["entries_number_mismatched"] = {
                "postgresql": sorted_pg_entries,
                "cassandra": sorted_cs_entries,
            }
            return result

        for i, sorted_cs_entry in enumerate(sorted_cs_entries):
            sorted_pg_entry = sorted_pg_entries[i]
            if (
                sorted_cs_entry == sorted_pg_entry
            ):  # (type, name, perms) ok is fine, continue
                continue

            if (
                sorted_pg_entry.type != sorted_cs_entry.type
                and sorted_pg_entry.name == sorted_cs_entry.name
                and sorted_pg_entry.perms == sorted_pg_entry.perms
            ):  # !type name perms
                result["type_mismatched"] = {
                    sorted_cs_entry.name: {
                        "postgresql": sorted_pg_entry.type,
                        "cassandra": sorted_cs_entry.type,
                    }
                }
            elif (
                sorted_pg_entry.type == sorted_cs_entry.type
                and sorted_pg_entry.name != sorted_cs_entry.name
                and sorted_pg_entry.perms == sorted_cs_entry.perms
            ):  # type !name perms
                result["name_mismatched"] = {
                    sorted_cs_entry.type: {
                        "postgresql": sorted_pg_entry.name,
                        "cassandra": sorted_cs_entry.name,
                    }
                }
            elif (
                sorted_pg_entry.type == sorted_cs_entry.type
                and sorted_pg_entry.name == sorted_cs_entry.name
                and sorted_pg_entry.perms != sorted_cs_entry.perms
            ):  # type name !perms

                result["perms_mismatched"] = {
                    sorted_cs_entry.name: {
                        "postgresql": oct(sorted_pg_entry.perms),
                        "cassandra": oct(sorted_cs_entry.perms),
                    }
                }
            elif (
                sorted_pg_entry.type != sorted_cs_entry.type
                and sorted_pg_entry.name != sorted_cs_entry.name
                and sorted_pg_entry.perms == sorted_cs_entry.perms
            ):  # !type !name perms
                result["type_and_name_mismatched"] = {
                    sorted_cs_entry.type: {
                        "postgresql": (
                            sorted_pg_entry.name,
                            oct(sorted_pg_entry.perms),
                        ),
                        "cassandra": (sorted_cs_entry.name, oct(sorted_cs_entry.perms)),
                    }
                }
            elif (
                sorted_pg_entry.type != sorted_cs_entry.type
                and sorted_pg_entry.name == sorted_cs_entry.name
                and sorted_pg_entry.perms != sorted_cs_entry.perms
            ):  # !type name !perms
                result["type_and_perms_mismatched"] = {
                    sorted_cs_entry.name: {
                        "postgresql": (
                            sorted_pg_entry.type,
                            oct(sorted_pg_entry.perms),
                        ),
                        "cassandra": (sorted_cs_entry.type, oct(sorted_cs_entry.perms)),
                    }
                }
            elif (
                sorted_pg_entry.type == sorted_cs_entry.type
                and sorted_pg_entry.name != sorted_cs_entry.name
                and sorted_pg_entry.perms != sorted_cs_entry.perms
            ):  # type !name !perms
                result["name_and_perms_mismatched"] = {
                    sorted_cs_entry.type: {
                        "postgresql": (
                            sorted_pg_entry.name,
                            oct(sorted_pg_entry.perms),
                        ),
                        "cassandra": (sorted_cs_entry.name, oct(sorted_cs_entry.perms)),
                    }
                }
            else:  # !type !name !perms (all different)
                result["type_and_name_and_perms_mismatched"] = {
                    "postgresql": (
                        sorted_pg_entry.type,
                        sorted_pg_entry.name,
                        oct(sorted_pg_entry.perms),
                    ),
                    "cassandra": (
                        sorted_cs_entry.type,
                        sorted_cs_entry.name,
                        oct(sorted_cs_entry.perms),
                    ),
                }
            if result:
                return result

    return result


for swhid in os.listdir(dir_volume):
    counter["total"] += 1
    id = swhid.split(":")[3]
    directory_id = hash_to_bytes(id)
    directory_raw_manifest = pg_storage.directory_get_raw_manifest([directory_id])
    pg_dirs = directory_get_many_with_possibly_duplicated_entries(
        pg_storage, [directory_id]
    )
    for d in pg_dirs:
        pg_dir = d[1]
    dirs = directory_get_many_with_possibly_duplicated_entries(
        pg_storage, [directory_id]
    )
    computed_hash = pg_dir.compute_hash()
    swhid_path = dir_volume + swhid
    with open(swhid_path + "/cassandra_representation") as f:
        cs = f.readlines()[-1].strip()

    if computed_hash != directory_id:
        counter["total_missing"] += 1
        counter["missing_corrupted_hash"] += 1
        continue

    results = compare_swhid_in_cassandra(swhid_path)
    if not results:
        counter["total_missing"] += 1
        counter["missing"] += 1
        continue

    keys = list(results.keys())
    if len(keys) != 1:
        print(f"Ensuring only one kind of error per swhid: <{swhid}> ({len(keys)})")
        pprint(results)
    key = keys[0]

    if key in counter:
        counter[key] += 1
    else:
        # we should never pass here
        # if we do, we missed a conditional in the discrepancy check algo
        counter["unknown"] += 1

    counter["total_mismatched"] += 1


summary = OrderedDict(
    {
        # inconsistencies when objects exist in cassandra but are failing the comparison
        "perms_mismatched": "objects with mismatched permissions",
        "type_mismatched": "objects with mismatched type",
        "name_mismatched": "objects with mismatched name",
        "type_and_perms_mismatched": "objects with mismatched type and perms",
        "type_and_name_mismatched": "objects with mismatched type and names",
        "name_and_perms_mismatched": "objects with mismatched name and perms",
        "type_and_name_and_perms_mismatched": "objects with mismatched type, name and perms",
        "entries_number_mismatched": "objects with mismatched number of entries",
        "unknown": "unknown (should be 0)",
        "total_mismatched": "total number of objects with mismatched directory entries (should be the total of all entries above)",
        # objects completely missing in cassandra
        "missing": "objects missing in cassandra",
        "missing_corrupted_hash": "objects missing with corrupted hash",
        "total_missing": "Total missing objects in cassandra",
        "total": "Total number of problematic objects",
    }
)

counter_computation_mismatched = 0
counter_missing_objects = 0
total_objects = 0
for key in summary.keys():
    print(f"{summary[key]}: %s" % counter[key])
    if "total" in key:
        print()
        continue

    if "mismatched" in key or "unknown" in key:
        counter_computation_mismatched += counter[key]
    elif "missing" in key:
        counter_missing_objects += counter[key]
    total_objects += counter[key]

print()

if counter["unknown"] != 0:  # ok
    print(
        f"Total number of unknown mismatched ({counter['unknown']}) should be 0 (we should be able to identify all mismatching problems)"
    )

if counter_computation_mismatched != counter["total_mismatched"]:
    print(
        f"Total number of directory with mismatched values ({counter_computation_mismatched}) should be the total number of issues ({counter['total_mismatched']})"
    )

if counter_missing_objects != counter["total_missing"]:
    print(
        f"Total number of objects missing in cassandra ({counter_missing_objects}) should be the total number of missing objects ({counter['total_missing']})"
    )

if total_objects != counter["total"]:
    print(
        f"Total number of objects ({total_objects}) should be the total number of objects ({counter['total']})"
    )
