"""
Reads objects from Kafka or Postgresql, and dumps recovered objects in
:file:`analyze_consistency_failures/`

Kafka
-----

Automatically manages parallelism and restart on error

Syntax::

    ./recheck_consistency.py kafka


Postgresql
----------

Checks all objects between two given hashes (inclusive).
Needs manual splitting and error management.

Syntax 

    ./recheck_consistency.py postgres {directory,release,revision} <sha1_git> <sha1_git>

For example, to handle the first 1/16th directories:

    ./recheck_consistency.py postgres directory 00 01
"""


import difflib
import hashlib
import json
import logging
import os
import multiprocessing
import pathlib
import pickle
import random
import secrets
import subprocess
import sys
import traceback
from typing import Dict

import dulwich.client
import dulwich.errors
import dulwich.object_store
import dulwich.pack
import dulwich.repo
import tqdm

from swh.graph.client import RemoteGraphClient, GraphArgumentException
from swh.loader.git.converters import (
    dulwich_tree_to_directory,
    dulwich_commit_to_revision,
    dulwich_tag_to_release,
)
from swh.model import model
from swh.model.swhids import ExtendedSWHID
from swh.model.hashutil import hash_to_bytes, hash_to_hex, hash_to_bytehex
from swh.model.git_objects import (
    directory_git_object,
    release_git_object,
    revision_git_object,
)
from swh.storage import get_storage
from swh.storage import backfill
from swh.core.api.classes import stream_results
from swh.core.utils import grouper

CLONES_BASE_DIR = pathlib.Path(
    "/srv/softwareheritage/cassandra-test-0/scratch/integrity_clones/"
).expanduser()

MANAGER = multiprocessing.Manager()

CLONED_ORIGINS_PATH = "analyze_consistency_failures/cloned_origins.json"
CLONED_ORIGINS: Dict[str, None]  # used like a set

if os.path.exists(CLONED_ORIGINS_PATH):
    with open(CLONED_ORIGINS_PATH, "rt") as fd:
        CLONED_ORIGINS = MANAGER.dict(json.load(fd))
        # CLONED_ORIGINS = {k: None for (k, v) in json.load(fd).items() if "linux" in k}
else:
    CLONED_ORIGINS = MANAGER.dict()
    # CLONED_ORIGINS = dict()

graph = RemoteGraphClient("http://graph.internal.softwareheritage.org:5009/graph/")
graph2 = RemoteGraphClient("http://localhost:5009/graph/")
logger = logging.getLogger(__name__)



################################
# Local clones manipulation


def get_clone_path(origin_url):
    if "linux" in origin_url:
        # linux.git is very big and there are lots of forks... let's fetch them all
        # in the same clone or it going to take forever to clone them all.
        return CLONES_BASE_DIR / "linux.git"
    else:
        origin_id = model.Origin(url=origin_url).swhid()
        dirname = f"{origin_id}_{origin_url.replace('/', '_')}"
        return CLONES_BASE_DIR / dirname


def clone(origin_url):
    print(f"Cloning {origin_url}")
    if "linux" in origin_url:
        # linux.git is very big and there are lots of forks... let's fetch them all
        # in the same clone or it going to take forever to clone them all.
        if origin_url in CLONED_ORIGINS:
            return
        clone_path = get_clone_path(origin_url)
        subprocess.run(
            ["git", "-C", clone_path, "fetch", origin_url],
            env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
        )
        CLONED_ORIGINS[origin_url] = None
    else:
        clone_path = get_clone_path(origin_url)
        if not clone_path.is_dir():
            # print("Cloning", origin_url)
            subprocess.run(
                ["git", "clone", "--bare", origin_url, clone_path],
                env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
            )


def get_object_from_clone(origin_url, obj_id):
    clone_path = get_clone_path(origin_url)
    try:
        repo = dulwich.repo.Repo(str(clone_path))
    except dulwich.errors.NotGitRepository:
        return None

    with repo:  # needed to avoid packfile fd leaks
        try:
            return repo[hash_to_bytehex(obj_id)]
        except dulwich.errors.ObjectFormatException:
            # fallback to git if dulwich can't parse it
            object_type = (
                subprocess.check_output(
                    ["git", "-C", clone_path, "cat-file", "-t", hash_to_hex(obj_id)]
                )
                .decode()
                .strip()
            )
            manifest = subprocess.check_output(
                ["git", "-C", clone_path, "cat-file", object_type, hash_to_hex(obj_id)]
            )
            print(f"Dulwich failed to parse: {manifest!r}")
            traceback.print_exc()


################################
# Object recovery from origins


def get_object_from_origins(swhid, stored_obj):
    print(f"Looking for {swhid}")
    obj_id = swhid.object_id
    (success, res) = get_origins(swhid, stored_obj)
    if not success:
        return (False, res)
    else:
        origins = res
    for origin_url in origins:
        if not origin_url.endswith(".git"):
            origin_url += ".git"
        if origin_url == "https://github.com/reingart/python.git":
            # Fails very often...
            raise
            # continue

        data = b"0032want " + hash_to_bytehex(obj_id) + b"\n"
        if swhid.object_type == model.ObjectType.REVISION:
            for parent in stored_obj.parents:
                data += b"0032have " + hash_to_bytehex(parent) + b"\n"
        elif swhid.object_type == model.ObjectType.RELEASE:
            data += b"0032have " + hash_to_bytehex(stored_obj.target) + b"\n"
        data += b"0000"
        data += b"0009done\n"

        clone_path = get_clone_path(origin_url)
        if not clone_path.is_dir():
            try:
                clone(origin_url)
            except subprocess.CalledProcessError:
                continue
        elif "linux" in origin_url:
            try:
                clone(origin_url)
            except subprocess.CalledProcessError:
                continue

        try:
            cloned_obj = get_object_from_clone(origin_url, obj_id)
        except KeyError:
            # try next origin
            continue
        if cloned_obj is None:
            return (False, "found_but_unparseable")
        break
    else:
        return (
            False,
            f"unrecoverable_{swhid.object_type.value}_no-origin "
            f"(tried: {' '.join(origins)})",
        )

    return (True, origin_url, cloned_obj)


def get_origins(swhid, stored_obj):
    dir_ = f"graph_backward_leaves/{hash_to_hex(swhid.object_id)[0:2]}"
    os.makedirs(dir_, exist_ok=True)
    graph_cache_file = f"{dir_}/{swhid}.txt"
    if os.path.isfile(graph_cache_file):
        with open(graph_cache_file) as fd:
            origin_swhids = [
                ExtendedSWHID.from_string(line.strip()) for line in fd if line.strip()
            ]
    else:
        for _ in range(10):
            try:
                origin_swhids = [
                    ExtendedSWHID.from_string(line)
                    for line in graph.leaves(swhid, direction="backward")
                    if line.startswith("swh:1:ori:")
                ]
            except GraphArgumentException:
                # try again with the local graph (more up to date, but partial)
                try:
                    origin_swhids = [
                        ExtendedSWHID.from_string(line)
                        for line in graph2.leaves(swhid, direction="backward")
                        if line.startswith("swh:1:ori:")
                    ]
                except GraphArgumentException:
                    return (
                        False,
                        f"unrecoverable_{swhid.object_type.value}_not-in-swh-graph",
                    )
                except:
                    pass
                else:
                    break
            except:
                raise
                pass
            else:
                break
        else:
            return (False, f"unrecoverable_{swhid.object_type.value}_swh-graph-crashes")
        tmp_path = graph_cache_file + ".tmp" + secrets.token_hex(8)
        with open(tmp_path, "wt") as fd:
            fd.write("\n".join(map(str, origin_swhids)))
            fd.write("\n")
        os.rename(tmp_path, graph_cache_file)  # atomic
    origins = [
        origin["url"]
        for origin in storage.origin_get_by_sha1(
            [origin_swhid.object_id for origin_swhid in origin_swhids]
        )
    ]

    # swh-graph results are in non-deterministic order; so a bit of sorting avoids
    # fetching lots of different forks of the same project.
    # And for big projects with lots of forks and/or broken commits,
    # let's manually hardcode the repo with the most commits.
    PRIOTIZED_ORIGINS = [
        "https://github.com/torvalds/linux.git",
        "https://github.com/git/git.git",
        "https://github.com/nixos/nixpkgs.git",
    ]
    origins.sort(key=lambda url: "" if url in PRIOTIZED_ORIGINS else url)

    return (True, origins)


################################
# Orchestration


def write_fixed_object(swhid, obj):
    dir_path = os.path.join("recheck_consistency", hash_to_hex(swhid.object_id)[0:2])
    os.makedirs(dir_path, exist_ok=True)
    with open(f"{dir_path}/{swhid}.pickle", "wb") as fd:
        pickle.dump(obj.to_dict(), fd)


def handle_mismatch(object_type, swhid, stored_obj):
    obj_id = swhid.object_id
    res = get_object_from_origins(swhid, stored_obj)
    if res[0]:
        # successfully recovered
        (_, origin_url, cloned_dulwich_obj) = res
    else:
        (_, bucket) = res
        print(f"Failed to recover {swhid}. Cause: {bucket}")
        return

    object_header = (
        cloned_dulwich_obj.type_name
        + b" "
        + str(cloned_dulwich_obj.raw_length()).encode()
        + b"\x00"
    )
    cloned_manifest = object_header + cloned_dulwich_obj.as_raw_string()
    rehash = hashlib.sha1(cloned_manifest).digest()
    assert (
        obj_id == rehash
    ), f"Mismatch between origin hash and original object: {obj_id.hex()} != {rehash.hex()}"

    if object_type == "revision":
        cloned_obj = dulwich_commit_to_revision(cloned_dulwich_obj)
        roundtripped_cloned_manifest = revision_git_object(cloned_obj)
    elif object_type == "directory":
        cloned_obj = dulwich_tree_to_directory(cloned_dulwich_obj)
        roundtripped_cloned_manifest = directory_git_object(cloned_obj)
    elif object_type == "release":
        cloned_obj = dulwich_tag_to_release(cloned_dulwich_obj)
        roundtripped_cloned_manifest = release_git_object(cloned_obj)
    else:
        assert False, object_type

    if roundtripped_cloned_manifest != cloned_manifest:
        print(f"manifest for {swhid} not round-tripped:")
        print(
            "\n".join(
                difflib.ndiff(
                    cloned_manifest.split(b"\x00", 1)[1]
                    .decode(errors="backslashreplace")
                    .split("\n"),
                    roundtripped_cloned_manifest.split(b"\x00", 1)[1]
                    .decode(errors="backslashreplace")
                    .split("\n"),
                )
            )
        )
        raise ValueError()

    write_fixed_object(swhid, cloned_obj)
    print(f"Recovered {swhid}")
    print(
        ",\n".join(
            difflib.ndiff(
                str(stored_obj).split(", "),
                str(cloned_obj).split(", "),
            )
        )
    )


def process_objects(object_type, objects):
    for object_ in objects:
        real_id = object_.compute_hash()
        if object_.id != real_id:
            handle_mismatch(object_type, object_.swhid(), object_)

    if random.randint(0, 100) == 0:
        # dump origins from time to time
        with open(CLONED_ORIGINS_PATH) as fd:
            CLONED_ORIGINS.update(json.load(fd))
        data = json.dumps(dict(CLONED_ORIGINS))

        tmp_path = CLONED_ORIGINS_PATH + ".tmp" + secrets.token_hex(8)
        with open(tmp_path, "wt") as fd:
            fd.write(data)
        os.rename(tmp_path, CLONED_ORIGINS_PATH)  # atomic


def process_dicts(all_dicts):
    for (object_type, dicts) in all_dicts.items():
        cls = getattr(model, object_type.capitalize())
        process_objects(object_type, map(cls.from_dict, dicts))


################################
# Reading existing data


def journal_main():
    from swh.journal.client import get_journal_client

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
        group_id="swh-vlorentz-T75-recheck-consistency",
        # object_types=["directory", "snapshot"],
        object_types=["directory", "revision", "snapshot", "release"],
        auto_offset_reset="earliest",
        **config,
    )

    try:
        client.process(process_dicts)
    except KeyboardInterrupt:
        print("Called Ctrl-C, exiting.")
        exit(0)


def postgres_main(object_type, start_object, end_object):
    storage = get_storage(
        cls="postgresql", db="service=swh-replica", objstorage={"cls": "memory"}
    )

    db = storage.get_db()
    cur = db.cursor()

    for range_start, range_end in backfill.RANGE_GENERATORS[object_type](
        start_object, end_object
    ):
        logger.info(
            "Processing %s range %s to %s",
            object_type,
            backfill._format_range_bound(range_start),
            backfill._format_range_bound(range_end),
        )

        objects = backfill.fetch(db, object_type, start=range_start, end=range_end)

        process_objects(object_type, objects)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    storage = get_storage(
        "pipeline",
        steps=[
            dict(cls="retry"),
            dict(
                cls="remote", url="http://webapp1.internal.softwareheritage.org:5002/"
            ),
        ],
    )

    try:
        (_, mode, *args) = sys.argv
        if mode == "kafka":
            () = args
        elif mode == "postgres":
            (type_, start_object, end_object) = args
        else:
            raise ValueError()
    except ValueError:
        print(__doc__)
        sys.exit(1)

    if mode == "kafka":
        journal_main()
    elif mode == "postgres":
        postgres_main(type_, start_object, end_object)
    else:
        assert False
