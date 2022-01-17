import hashlib
import itertools
import os
import pickle
import pprint
import sys

import attr

import swh.model.git_objects as git_objects
from swh.model.hashutil import bytehex_to_hash, hash_to_bytes
import swh.model.model as model
from swh.model.model import Person

digest = pickle.load(open("analyze_consistency_failures/results.pickle", "rb"))


def directory_identifier_without_sorting(directory):
    """Like swh.model.git_objects.directory_git_object, but does not sort entries."""
    components = []

    for entry in directory.entries:
        components.extend(
            [
                git_objects._perms_to_bytes(entry.perms),
                b"\x20",
                entry.name,
                b"\x00",
                entry.target,
            ]
        )
    git_object = git_objects.format_git_object_from_parts("tree", components)
    return hashlib.new("sha1", git_object).hexdigest()


def process_objects(all_objects):
    for (object_type, objects) in all_objects.items():
        assert object_type == "directory"
        for object_dict in objects:
            object_ = model.Directory.from_dict(object_dict)
            if object_.id in digest["weird-dir_with_unknown_sort_ok_in_kafka"]:
                real_id = object_.compute_hash()
                id_without_sorting = directory_identifier_without_sorting(object_)
                assert object_.id != real_id

                suffix = ""
                if id_without_sorting == object_.id.hex():
                    print("wtf? mismatched hashes:",  id_without_sorting, object_.id.hex())
                    suffix = ".failedrecompute"

                # Just to be sure it's round-trippable
                assert directory_identifier_without_sorting(model.Directory.from_dict(object_.to_dict()))

                swhid = f"swh:1:dir:{object_.id.hex()}"
                print(f"Dumping {swhid}")

                dir_path = os.path.join(
                    "analyze_consistency_failures", swhid[0:2]
                )
                os.makedirs(dir_path, exist_ok=True)
                with open(f"{dir_path}/{swhid}.from_kafka{suffix}.pickle" + suffix, "wb") as fd:
                    pickle.dump(object_dict, fd)


def main():
    from swh.journal.client import get_journal_client

    # import logging
    # logging.basicConfig(level=logging.DEBUG)

    config = {
        "sasl.mechanism": "SCRAM-SHA-512",
        "security.protocol": "SASL_SSL",
        "sasl.username": "swh-vlorentz",
        "sasl.password": os.environ["KAFKA_SASL_PASSWORD"],
        "privileged": True,
        "message.max.bytes": 524288000,
        # "debug": "consumer",
        # "debug": "all",
    }

    client = get_journal_client(
        "kafka",
        brokers=[f"broker{i}.journal.softwareheritage.org:9093" for i in range(1, 5)],
        group_id="swh-vlorentz-T3552-backup-weird-dirs-ok-in-kafka",
        # object_types=["directory", "snapshot"],
        object_types=["directory"],
        auto_offset_reset="earliest",
        **config,
    )

    try:
        client.process(process_objects)
    except KeyboardInterrupt:
        print("Called Ctrl-C, exiting.")
        exit(0)


if __name__ == "__main__":
    main()
