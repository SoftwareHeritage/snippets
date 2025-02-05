import collections
import difflib
import functools
import gc
import itertools
import json
import hashlib
import multiprocessing
import multiprocessing.dummy
import operator
import os
import pathlib
import pickle
import re
import secrets
import signal
import socket
import ssl
import subprocess
import sys
import traceback
from typing import Dict
import urllib.parse

import attr
import dulwich.client
import dulwich.errors
import dulwich.object_store
import dulwich.pack
import dulwich.repo
import tqdm

from swh.core.api.classes import stream_results_optional
from swh.core.utils import grouper
from swh.graph.client import RemoteGraphClient, GraphArgumentException
from swh.loader.git.converters import (
    dulwich_tree_to_directory,
    dulwich_commit_to_revision,
)
from swh.model.hashutil import hash_to_bytes, hash_to_hex, hash_to_bytehex
from swh.model.git_objects import (
    directory_git_object,
    release_git_object,
    revision_git_object,
    format_git_object_from_parts,
    _perms_to_bytes,
    directory_entry_sort_key,
)
from swh.model.model import (
    Directory,
    Origin,
    Person,
    RevisionType,
    Timestamp,
    TimestampWithTimezone,
)
from swh.model.swhids import ObjectType, CoreSWHID, ExtendedSWHID
from swh.storage import get_storage

CLONES_BASE_DIR = pathlib.Path(
    "/srv/softwareheritage/cassandra-test-0/scratch/integrity_clones/"
).expanduser()

MISMATCH = re.compile(
    "Checksum mismatch on (?P<obj_type>[a-z]+): (?P<obj_id>[0-9a-f]{40}) in journal, but recomputed as .*"
)
MISMATCH_SIGNED_OFF = re.compile(
    "Possibly missing 'gpgsig' header: (?P<obj_id>[0-9a-f]{40})"
)
MISMATCH_HG_TO_GIT = re.compile(
    "Possibly missing 'HG:extra' header: (?P<obj_id>[0-9a-f]{40})"
)
SVN_MISMATCH = re.compile("Possibly unfixable SVN revision: (?P<obj_id>[0-9a-f]{40})")
FIXABLE = re.compile(
    r"Fixable (?P<obj_type>[a-z]+) (?P<obj_id>[0-9a-f]{40}) \((?P<how>[^)]*)\)"
)
UNORDERED_DIRECTORY = re.compile(
    r"Weird directory checksum (?P<obj_id>[0-9a-f]{40}) \(computed without sorting\)"
)
NOISE = re.compile(r"Called Ctrl-C\, exiting\.")

REVISION_BUCKETS_TO_RECOVER = (
    "fixable_trivial_revision",
    "mismatch_misc_revision",
    "mismatch_hg_to_git",
    "unrecoverable_rev_not-in-swh-graph",
    "unrecoverable_rev_swh-graph-crashes",
    "unrecoverable_rev_no-origin",
)

RELEASE_BUCKETS_TO_RECOVER = (
    "mismatch_misc_release",
    "unrecoverable_rel_swh-graph-crashes",
    "unrecoverable_rel_not-in-swh-graph",
    "unrecoverable_rel_no-origin",
)

DIRECTORY_BUCKETS_TO_RECOVER = (
    "fixable_trivial_directory",
    "mismatch_misc_directory",
    "unrecoverable_dir_no-origin",
    "recoverable_misc_dir",
    "weird_misc_dir",
    "recoverable_disordered_dir",
    "weird_disordered_dir",
    "recoverable_unordered_dir",
    "weird_unordered_dir",
    "weird_dir_perms_misc",
    "weird-dir_with_unknown_sort",
    "weird-dir_with_unknown_sort_ok_in_kafka",
    "weird-dir_with_unknown_sort_ok_in_pg",
    "weird-dir_with_backfiller_partial_sort",
    "weird_misc_dir",
    "weird-padded_perms_40000",
    "weird-padded_perms_40000_except_1",
)

ENCODINGS = (
    b"SHIFT_JIS",
    b"Shift-JIS",
    b"shift-jis",
    b"shift_jis",
    b"Shift_JIS",
    b"SJIS",
    b"iso8859-1",
    b"iso-8859-1",
    b"ISO-8859-1",
    b" ISO-8859-1",
    b"iso8859-15",
    b"ISO-8859-1]",
    b"UTF8]",
    b"UTF-8 UTF8",
    b"{utf-8}",
    b"iso-latin-1",
    b"'Latin-1'",
    b"ISO8859-15",
    b"iso-8859-15",
    b"ISO-8859-15",
    b"euc-kr",
    b"EUC-JP",
    b"koi8-r",
    b"big5",
    b"ISO-8859-2",
    b"iso8859-2",
    b"ru_RU.KOI8-R",
    b"cp1250",
    b"CP-1250",
    b"cp-1251",
    b"CP-1252",
    b"cp932",
    b"latin-1",
    b"Latin-1",
    b"latin1",
    b"Latin1",
    b"ISO-2022-JP",
    b"KOI8-R",
    b"windows-1250",
    b"window-1252",
    b"windows-1252",
    b"'windows-1252'",
    b"WINDOWS-1251",
    b"Windows-1257",
    b"euckr",
    b"ISO-88592",
    b"iso10646-1",
    b"iso-8859-7",
    b"=",
    b"CP950",
    b"win",
    b"win-1251",
    b"utf",
    b"{UTF-8|GBK}",
    b"GBKe",
    b"UTF-16",
    b"utf-16",
    b"GB18030",
    b"GB23",
    b"true",  # wat
    b"BIG5",
    b"cp866",
    b"CP-1251",
    b"cp1251",
    b"cp949",
    b"latin2",
    b"utf-8logoutputencoding=gbk",  # wat
    b"gb18030",
    b"UTF-8-MAC UTF8-MAC",
    b"cp",
    b"ANSI",
    b"ru_RU.UTF8",
    b"ru_RU.utf8",
    b"UTF-8",
    b"utf-8",
    b"zh_CN.GB18030",
    b"iso-2022-jp",
    b"en_US.UTF-8",
    b"it_IT.UTF8",
    b"dos",
    b"iso8859-13",
    b"iso-8851-9",
)


ZERO_TIMESTAMP = TimestampWithTimezone(
    Timestamp(seconds=0, microseconds=0), offset=0, negative_utc=False
)

graph = RemoteGraphClient("http://graph.internal.softwareheritage.org:5009/graph/")
graph2 = RemoteGraphClient("http://localhost:5009/graph/")


REVISIONS = {}
RELEASES = {}
DIRECTORIES = {}

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


def get_clone_path(origin_url):
    if "linux" in origin_url:
        # linux.git is very big and there are lots of forks... let's fetch them all
        # in the same clone or it going to take forever to clone them all.
        return CLONES_BASE_DIR / "linux.git"
    else:
        origin_id = Origin(url=origin_url).swhid()
        dirname = f"{origin_id}_{origin_url.replace('/', '_')}"
        return CLONES_BASE_DIR / dirname


def clone(origin_url):
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


def _load_revisions(ids):
    ids = list(ids)
    storage = get_storage(
        "remote", url="http://webapp1.internal.softwareheritage.org:5002/"
    )
    return dict(zip(ids, storage.revision_get(ids)))


def _load_releases(ids):
    ids = list(ids)
    storage = get_storage(
        "remote", url="http://webapp1.internal.softwareheritage.org:5002/"
    )
    return dict(zip(ids, storage.release_get(ids)))


def _load_directory(id):
    storage = get_storage(
        "remote", url="http://webapp1.internal.softwareheritage.org:5002/"
    )
    try:
        entries = tuple(
                stream_results_optional(storage.directory_get_entries, id)
            )
    except Exception as e:
        assert "is not a valid directory entry name." in e.args[0]["args"][0], e.args[0]
        return None
    try:
        return Directory(
            id=id,
            entries=entries,
        )
    except ValueError as e:
        assert "duplicated entry name" in e.args[0]
        return None

def get_buckets(digest, names):
    """returns `digest[names[0]] | digest[names[1]] | ...`"""
    return functools.reduce(operator.or_, (digest[name] for name in names), set())


def main(input_fd):
    digest = collections.defaultdict(set)

    """
    # Parse logs from check_consistency.py to 'digest'
    for line in tqdm.tqdm(
        list(input_fd), desc="parsing input", unit="line", unit_scale=True
    ):
        handle_line(digest, line)
    """

    print("Preloading corrupt objects...")
    try:
        with open("analyze_consistency_failures/corrupt_revisions.pickle", "rb") as fd:
            REVISIONS.update(pickle.load(fd))
    except:
        pass
    try:
        with open("analyze_consistency_failures/corrupt_releases.pickle", "rb") as fd:
            RELEASES.update(pickle.load(fd))
    except:
        pass
    try:
        with open("analyze_consistency_failures/corrupt_directories.pickle", "rb") as fd:
            DIRECTORIES.update(pickle.load(fd))
    except:
        pass
    print("\tDone")
    # preload revisions in batches
    # revision_id_groups = list(grouper(digest["mismatch_misc_revision"], 1000))[0:100]
    # revision_id_groups = list(grouper(digest["mismatch_hg_to_git"], 1000))
    revision_id_groups = list(
        grouper(
            [
                id_
                for id_ in get_buckets(digest, REVISION_BUCKETS_TO_RECOVER)
                if id_ not in REVISIONS
            ],
            1000,
        )
    )
    with multiprocessing.dummy.Pool(10) as p:
        for revisions in tqdm.tqdm(
            p.imap_unordered(_load_revisions, revision_id_groups),
            desc="loading revisions",
            unit="k revs",
            total=len(revision_id_groups),
        ):
            REVISIONS.update(revisions)

    release_id_groups = list(
        grouper(
            [
                id_
                for id_ in get_buckets(digest, RELEASE_BUCKETS_TO_RECOVER)
                if id_ not in RELEASES
            ],
            1000,
        )
    )
    with multiprocessing.dummy.Pool(10) as p:
        for releases in tqdm.tqdm(
            p.imap_unordered(_load_releases, release_id_groups),
            desc="loading releases",
            unit="k rels",
            total=len(release_id_groups),
        ):
            RELEASES.update(releases)

    directory_ids = [
                id_
                for id_ in get_buckets(digest, DIRECTORY_BUCKETS_TO_RECOVER)
                if id_ not in DIRECTORIES
            ]
    with multiprocessing.dummy.Pool(10) as p:
        for (id, directory) in tqdm.tqdm(
            zip(directory_ids, p.imap(_load_directory, directory_ids, chunksize=100)),
            desc="loading directories",
            unit="dirs",
            total=len(directory_ids),
        ):
            if directory:
                DIRECTORIES[id] = directory

    for (type_, obj_ids) in sorted(digest.items()):
        print(f"{len(obj_ids)}\t{type_}")

    print("Dumping corrupt objects...")
    with open("analyze_consistency_failures/corrupt_releases.pickle", "wb") as fd:
        pickle.dump(RELEASES, fd)
    with open("analyze_consistency_failures/corrupt_revisions.pickle", "wb") as fd:
        pickle.dump(REVISIONS, fd)
    with open("analyze_consistency_failures/corrupt_directories.pickle", "wb") as fd:
        pickle.dump(DIRECTORIES, fd)
    print("\tDone")

    # oops, accidentally put them in the wrong bucket
    digest["unrecoverable_dir_no-origin"] -= digest[
        "weird-dir_with_unknown_sort_ok_in_kafka"
    ]

    # Prevent the GC from collecting or moving existing objects; so the kernel does
    # not need to CoW them in the worker processes.
    gc.freeze()

    # Try to fix objects one by one
    jobs = (
        [
            (try_directory_recovery, bucket)
            for bucket in list(DIRECTORY_BUCKETS_TO_RECOVER)
            + [bucket for bucket in digest if bucket.startswith("weird-dir")]
        ]
        + [(try_revision_recovery, bucket) for bucket in REVISION_BUCKETS_TO_RECOVER]
        + [(try_release_recovery, bucket) for bucket in RELEASE_BUCKETS_TO_RECOVER]
    )
    with multiprocessing.Pool(32, maxtasksperchild=100) as p:
        for (f, initial_bucket) in jobs:
            f = functools.partial(f, initial_bucket=initial_bucket)
            obj_ids = list(digest.pop(initial_bucket, []))
            assert all(isinstance(id_, bytes) for id_ in obj_ids)
            for (i, (obj_id, new_key)) in enumerate(
                tqdm.tqdm(
                    p.imap_unordered(f, obj_ids, chunksize=100),
                    desc=f"recovering {initial_bucket}",
                    unit="obj",
                    total=len(obj_ids),
                    smoothing=0.01,
                )
            ):
                digest[new_key].add(obj_id)

                if i % 10_000 == 0:
                    data = json.dumps(dict(CLONED_ORIGINS))
                    with open(CLONED_ORIGINS_PATH, "wt") as fd:
                        fd.write(data)

            for (type_, obj_ids) in sorted(digest.items()):
                print(f"{len(obj_ids)}\t{type_}")

            with open("analyze_consistency_failures/results.pickle", "wb") as fd:
                pickle.dump(dict(digest), fd)


def write_fixed_manifest(swhid, manifest):
    dir_path = os.path.join(
        "analyze_consistency_failures", hash_to_hex(swhid.object_id)[0:2]
    )
    os.makedirs(dir_path, exist_ok=True)
    with open(f"{dir_path}/{swhid}.git_manifest", "wb") as fd:
        fd.write(manifest)


def write_fixed_object(swhid, obj):
    dir_path = os.path.join(
        "analyze_consistency_failures", hash_to_hex(swhid.object_id)[0:2]
    )
    os.makedirs(dir_path, exist_ok=True)
    with open(f"{dir_path}/{swhid}.pickle", "wb") as fd:
        pickle.dump(obj.to_dict(), fd)


def handle_line(digest, line):
    line = line.strip()
    if not line:
        return
    if NOISE.fullmatch(line):
        return
    m = MISMATCH.fullmatch(line)
    if m:
        obj_type = m.group("obj_type")
        obj_id = m.group("obj_id")
        digest[f"mismatch_misc_{obj_type}"].add(hash_to_bytes(obj_id))
        return
    m = MISMATCH_SIGNED_OFF.fullmatch(line)
    if m:
        obj_id = m.group("obj_id")
        digest["mismatch_misc_revision"].add(hash_to_bytes(obj_id))
        return
    m = MISMATCH_HG_TO_GIT.fullmatch(line)
    if m:
        obj_id = m.group("obj_id")
        digest["mismatch_hg_to_git"].add(hash_to_bytes(obj_id))
        return
    m = SVN_MISMATCH.fullmatch(line)
    if m:
        digest["mismatch_misc_revision_svn"].add(hash_to_bytes(m.group("obj_id")))
        return
    m = FIXABLE.fullmatch(line)
    if m:
        digest["fixable_trivial_" + m.group("obj_type")].add(
            hash_to_bytes(m.group("obj_id"))
        )
        return
    m = UNORDERED_DIRECTORY.fullmatch(line)
    if m:
        digest["weird_unordered_dir"].add(hash_to_bytes(m.group("obj_id")))
        return

    # Two messages sometimes ended up on the same line; try to split it
    for regexp in (
        MISMATCH,
        MISMATCH_SIGNED_OFF,
        MISMATCH_HG_TO_GIT,
        SVN_MISMATCH,
        FIXABLE,
        UNORDERED_DIRECTORY,
        NOISE,
    ):
        match = regexp.match(line)
        if match:
            first_message = match.group(0)
            handle_line(digest, first_message)
            handle_line(digest, line[len(first_message) :])
            break
    else:
        assert False, line


def try_revision_recovery(obj_id, initial_bucket):
    return (obj_id, _try_recovery(ObjectType.REVISION, obj_id, initial_bucket))


def try_release_recovery(obj_id, initial_bucket):
    return (obj_id, _try_recovery(ObjectType.RELEASE, obj_id, initial_bucket))


def try_directory_recovery(obj_id, initial_bucket):
    try:
        return (obj_id, _try_recovery(ObjectType.DIRECTORY, obj_id, initial_bucket))
    except KeyboardInterrupt:
        raise
    except:
        import traceback

        traceback.print_exc()
        raise


def _try_recovery(obj_type, obj_id, initial_bucket):
    """Try fixing the given obj_id, and returns what digest key it should be added to"""
    obj_id = hash_to_bytes(obj_id)
    swhid = CoreSWHID(object_type=obj_type, object_id=obj_id)
    storage = get_storage(
        "pipeline",
        steps=[
            dict(cls="retry"),
            dict(
                cls="remote", url="http://webapp1.internal.softwareheritage.org:5002/"
            ),
        ],
    )

    if obj_type == ObjectType.REVISION:
        stored_obj = REVISIONS[obj_id]
        if stored_obj is None:
            return "revision_missing_from_storage"
        if stored_obj.type not in (RevisionType.GIT, RevisionType.SUBVERSION):
            return f"mismatch_misc_{stored_obj.type.value}"
        stored_manifest = revision_git_object(stored_obj)
    elif obj_type == ObjectType.RELEASE:
        stored_obj = RELEASES[obj_id]
        if stored_obj is None:
            return "release_missing_from_storage"
        stored_manifest = release_git_object(stored_obj)
    elif obj_type == ObjectType.DIRECTORY:
        stored_obj = DIRECTORIES.get(obj_id)
        if stored_obj is None:
            stored_manifest = None
        else:
            stored_manifest = directory_git_object(stored_obj)
    else:
        assert False, obj_type

    if stored_obj is not None:
        assert obj_id == stored_obj.id
        if obj_id == stored_obj.compute_hash():
            # Wtf? the hash did not match when pulled from kafka, but it does when pulled
            # from swh-storage?
            write_fixed_object(swhid, stored_obj)
            return "fine_in_storage"

    if obj_type == ObjectType.REVISION:
        bucket = try_fix_revision(swhid, stored_obj, stored_manifest)
    elif obj_type == ObjectType.RELEASE:
        bucket = try_fix_release(swhid, stored_obj, stored_manifest)
    elif obj_type == ObjectType.DIRECTORY:
        if stored_obj is None:
            bucket = None
        else:
            bucket = try_fix_directory(swhid, stored_obj, stored_manifest)
    else:
        assert False, obj_id

    if bucket is not None:
        assert isinstance(bucket, str), repr(bucket)
        return bucket

    assert False or "swh:1:dir:" in str(swhid), swhid

    if initial_bucket in (
        "weird_unordered_dir",
        "weird-dir_with_unknown_sort_ok_in_kafka",
    ):
        return f"weird-dir_with_unknown_sort_ok_in_kafka"

    if obj_type == ObjectType.REVISION and stored_obj.type != RevisionType.GIT:
        print("not fixed", stored_obj.id.hex())
        print("\t", get_origins(swhid, stored_obj))
        print("\t", stored_obj)
        return initial_bucket

    res = get_object_from_origins(swhid, stored_obj)
    if res[0]:
        (_, origin_url, cloned_obj) = res
    else:
        (_, bucket) = res
        assert isinstance(bucket, str), repr(bucket)
        return bucket

    object_header = (
        cloned_obj.type_name + b" " + str(cloned_obj.raw_length()).encode() + b"\x00"
    )
    cloned_manifest = object_header + cloned_obj.as_raw_string()
    rehash = hashlib.sha1(cloned_manifest).digest()
    assert (
        obj_id == rehash
    ), f"Mismatch between origin hash and original object: {obj_id.hex()} != {rehash.hex()}"

    if obj_type == ObjectType.REVISION:
        bucket = try_recover_revision(
            swhid, stored_obj, stored_manifest, cloned_obj, cloned_manifest, origin_url
        )
    elif obj_type == ObjectType.RELEASE:
        bucket = try_recover_release(
            swhid, stored_obj, stored_manifest, cloned_obj, cloned_manifest, origin_url
        )
    elif obj_type == ObjectType.DIRECTORY:
        bucket = try_recover_directory(
            swhid, stored_obj, stored_manifest, cloned_obj, cloned_manifest, origin_url
        )
    else:
        assert False, obj_id

    if bucket is not None:
        assert isinstance(bucket, str), repr(bucket)
        return bucket

    try:
        if obj_type == ObjectType.REVISION:
            cloned_obj = dulwich_commit_to_revision(cloned_obj)
            roundtripped_cloned_manifest = revision_git_object(cloned_obj)
        elif obj_type == ObjectType.DIRECTORY:
            cloned_obj = dulwich_tree_to_directory(cloned_obj)
            roundtripped_cloned_manifest = directory_git_object(cloned_obj)
        else:
            assert False, obj_type
    except:
        roundtripped_cloned_manifest = None

    if roundtripped_cloned_manifest == cloned_manifest:
        if obj_type == ObjectType.DIRECTORY and [
            (entry.name, entry.target) for entry in stored_obj.entries
        ] == [(entry.name, entry.target) for entry in cloned_obj.entries]:
            write_fixed_object(swhid, cloned_obj)
            return f"weird_dir_perms_misc"
        else:
            write_fixed_object(swhid, cloned_obj)
            return f"recoverable_misc_{obj_type.value}"
    else:
        write_fixed_manifest(swhid, cloned_manifest)
        return f"weird_misc_{obj_type.value}"


def try_fix_revision(swhid, stored_obj, stored_manifest):
    obj_id = swhid.object_id

    if stored_obj.type == RevisionType.SUBVERSION:
        for i in range(0, 10):
            fixed_stored_obj = attr.evolve(
                stored_obj,
                date=attr.evolve(
                    stored_obj.date,
                    timestamp=attr.evolve(
                        stored_obj.date.timestamp,
                        microseconds=stored_obj.date.timestamp.microseconds + i,
                    ),
                ),
                committer_date=attr.evolve(
                    stored_obj.committer_date,
                    timestamp=attr.evolve(
                        stored_obj.committer_date.timestamp,
                        microseconds=stored_obj.committer_date.timestamp.microseconds
                        + i,
                    ),
                ),
            )
            if fixed_stored_obj.compute_hash() == obj_id:
                write_fixed_object(swhid, fixed_stored_obj)
                return f"fixable_truncated_microseconds_{i}"

    # Try add '\n' to the gpgsig
    if b"gpgsig" in dict(stored_obj.extra_headers):
        fixed_stored_obj = attr.evolve(
            stored_obj,
            extra_headers=(
                (k, v + b"\n" if k == b"gpgsig" else v)
                for (k, v) in stored_obj.extra_headers
            ),
        )
        if fixed_stored_obj.compute_hash() == obj_id:
            write_fixed_object(swhid, fixed_stored_obj)
            return f"fixable_add_newline_gpgsig"

    # Try removing '\n' from the gpgsig
    if b"gpgsig" in dict(stored_obj.extra_headers):
        fixed_stored_obj = attr.evolve(
            stored_obj,
            extra_headers=(
                (k, v[0:-1] if k == b"gpgsig" and v.endswith(b"\n") else v)
                for (k, v) in stored_obj.extra_headers
            ),
        )
        if fixed_stored_obj.compute_hash() == obj_id:
            write_fixed_object(swhid, fixed_stored_obj)
            return f"fixable_rm_newline_gpgsig"

    # Try fixing item 1 on https://forge.softwareheritage.org/T75#70553
    # (gpgsig header badly formatted)
    if b"gpgsig" in dict(stored_obj.extra_headers):
        gpgsig = dict(stored_obj.extra_headers)[b"gpgsig"]
        fixed_stored_obj = attr.evolve(
            stored_obj,
            extra_headers=((b"gpgsig", gpgsig),) + tuple(
                (k, v) for (k, v) in stored_obj.extra_headers if k != b"gpgsig"
            ),
        )
        if fixed_stored_obj.compute_hash() == obj_id:
            write_fixed_object(swhid, fixed_stored_obj)
            return f"fixable_gpgsig_first"

    # Try removing '\n' from the mergetag
    if b"mergetag" in dict(stored_obj.extra_headers):
        fixed_stored_obj = attr.evolve(
            stored_obj,
            extra_headers=(
                (k, v[0:-1] if k == b"mergetag" and v.endswith(b"\n") else v)
                for (k, v) in stored_obj.extra_headers
            ),
        )
        if fixed_stored_obj.compute_hash() == obj_id:
            write_fixed_object(swhid, fixed_stored_obj)
            return f"fixable_rm_newline_mergetag"

    # Try adding an encoding header
    if b"encoding" not in dict(stored_obj.extra_headers):
        for encoding in ENCODINGS:
            fixed_stored_obj = attr.evolve(
                stored_obj,
                extra_headers=(*stored_obj.extra_headers, (b"encoding", encoding)),
            )
            if fixed_stored_obj.compute_hash() == obj_id:
                write_fixed_object(swhid, fixed_stored_obj)
                return f"fixable_add_encoding"
            if fixed_stored_obj.message is not None:
                for _ in range(3):
                    fixed_stored_obj = attr.evolve(
                        fixed_stored_obj,
                        message=b"\n" + (fixed_stored_obj.message or b""),
                    )
                    if fixed_stored_obj.compute_hash() == obj_id:
                        write_fixed_object(swhid, fixed_stored_obj)
                        return f"fixable_add_encoding_and_leading_newlines"

    # Try moving the nonce at the end
    for header in (b"nonce", b"x-nonce"):
        if header in dict(stored_obj.extra_headers):
            fixed_stored_obj = attr.evolve(
                stored_obj,
                extra_headers=(
                    *[(k, v) for (k, v) in stored_obj.extra_headers if k != header],
                    *[(k, v) for (k, v) in stored_obj.extra_headers if k == header],
                ),
            )
            if fixed_stored_obj.compute_hash() == obj_id:
                write_fixed_object(swhid, fixed_stored_obj)
                return "fixable_move_nonce"

    # Try adding leading space to email
    # (very crude, this assumes author = committer)
    fullname = stored_obj.author.fullname.replace(b" <", b" < ")
    fixed_stored_obj = attr.evolve(
        stored_obj,
        author=Person(fullname=fullname, name=b"", email=b""),
        committer=Person(fullname=fullname, name=b"", email=b""),
    )
    if fixed_stored_obj.compute_hash() == obj_id:
        write_fixed_object(swhid, fixed_stored_obj)
        return "fixable_author_email_leading_space"

    # Try removing space between name and email
    # (very crude, this assumes author = committer)
    fixed_stored_obj = attr.evolve(
        stored_obj,
        author=Person(fullname=stored_obj.author.fullname.replace(b" <", b"<"), name=b"", email=b""),
        committer=Person(fullname=stored_obj.committer.fullname.replace(b" <", b"<"), name=b"", email=b""),
    )
    if fixed_stored_obj.compute_hash() == obj_id:
        write_fixed_object(swhid, fixed_stored_obj)
        return "fixable_author_email_no_space"

    # Try adding trailing spaces to email
    for trailing in [b" " * i for i in range(8)] + [b"\r", b" \r", b"\t"]:
        for (pad_author, pad_committer) in ((1, 0), (0, 1), (1, 1)):
            fixed_stored_obj = attr.evolve(
                stored_obj,
                author=attr.evolve(
                    stored_obj.author,
                    fullname=stored_obj.author.fullname[0:-1] + trailing + b">",
                )
                if pad_author
                else stored_obj.author,
                committer=attr.evolve(
                    stored_obj.committer,
                    fullname=stored_obj.committer.fullname[0:-1] + trailing + b">",
                )
                if pad_committer
                else stored_obj.committer,
            )
            if fixed_stored_obj.compute_hash() == obj_id:
                write_fixed_object(swhid, fixed_stored_obj)
                return "fixable_author_email_trailing_whitespace"

    # Try adding carriage return to name *and* email
    for (pad_author, pad_committer) in ((1, 0), (0, 1), (1, 1)):
        fixed_stored_obj = attr.evolve(
            stored_obj,
            author=attr.evolve(
                stored_obj.author,
                fullname=stored_obj.author.fullname.replace(b" <", b"\r <").replace(
                    b">", b"\r>"
                ),
            )
            if pad_author
            else stored_obj.author,
            committer=attr.evolve(
                stored_obj.committer,
                fullname=stored_obj.committer.fullname.replace(b" <", b"\r <").replace(
                    b">", b"\r>"
                ),
            )
            if pad_committer
            else stored_obj.committer,
        )
    if fixed_stored_obj.compute_hash() == obj_id:
        write_fixed_object(swhid, fixed_stored_obj)
        return "fixable_author_name_email_trailing_whitespace"

    # Try adding spaces before the name
    for author_pad in range(0, 4):
        for committer_pad in range(0, 4):
            fixed_stored_obj = attr.evolve(
                stored_obj,
                author=attr.evolve(
                    stored_obj.author,
                    fullname=b" " * author_pad + stored_obj.author.fullname,
                ),
                committer=attr.evolve(
                    stored_obj.committer,
                    fullname=b" " * committer_pad + stored_obj.committer.fullname,
                ),
            )
            if fixed_stored_obj.compute_hash() == obj_id:
                write_fixed_object(swhid, fixed_stored_obj)
                return "fixable_author_leading_spaces"

    # Try adding spaces between name and email
    for i in (0, 1, 2, 4, 5, 8, 16, 32):
        fullname = stored_obj.author.fullname.replace(b" <", b" " * i + b"<", 1)
        fixed_stored_obj = attr.evolve(
            stored_obj,
            author=Person(fullname=fullname, name=b"", email=b""),
            committer=Person(fullname=fullname, name=b"", email=b""),
        )
        if fixed_stored_obj.compute_hash() == obj_id:
            write_fixed_object(swhid, fixed_stored_obj)
            return "fixable_author_middle_spaces"

    # Try again but with differing values
    for committer_padding in (0, 1, 2, 4, 5, 8):
        for author_padding in (0, 1, 2, 4, 5, 8):
            fixed_stored_obj = attr.evolve(
                stored_obj,
                author=Person(
                    fullname=stored_obj.author.fullname.replace(
                        b" <", b" " + b" " * author_padding + b"<"
                    ),
                    name=b"",
                    email=b"",
                ),
                committer=Person(
                    fullname=stored_obj.committer.fullname.replace(
                        b" <", b" " + b" " * committer_padding + b"<"
                    ),
                    name=b"",
                    email=b"",
                ),
            )
            if fixed_stored_obj.compute_hash() == obj_id:
                write_fixed_object(swhid, fixed_stored_obj)
                return "fixable_author_middle_spaces"

    # Try adding spaces around the name
    for i in range(1, 4):
        fullname = b" " * i + stored_obj.author.fullname.replace(
            b" <", b" " * i + b" <"
        )
        fixed_stored_obj = attr.evolve(
            stored_obj,
            author=Person(fullname=fullname, name=b"", email=b""),
            committer=Person(fullname=fullname, name=b"", email=b""),
        )
        if fixed_stored_obj.compute_hash() == obj_id:
            write_fixed_object(swhid, fixed_stored_obj)
            return "fixable_author_leading_and_middle_spaces"

    # Try adding spaces after the fullname
    fullname = stored_obj.author.fullname + b" "
    fixed_stored_obj = attr.evolve(
        stored_obj,
        author=Person(fullname=fullname, name=b"", email=b""),
        committer=Person(fullname=fullname, name=b"", email=b""),
    )
    if fixed_stored_obj.compute_hash() == obj_id:
        write_fixed_object(swhid, fixed_stored_obj)
        return "fixable_author_trailing_space"
    for _ in range(2):
        fixed_stored_obj = attr.evolve(
            fixed_stored_obj, message=b"\n" + (fixed_stored_obj.message or b"")
        )
        if fixed_stored_obj.compute_hash() == obj_id:
            write_fixed_object(swhid, fixed_stored_obj)
            return "fixable_author_trailing_space_and_leading_newlines"

    # Try adding leading newlines
    if stored_obj.message is not None:
        fixed_stored_obj = stored_obj
        for _ in range(23):  # seen in the wild: any from 1 to 8, 13, 15, 22, 23
            fixed_stored_obj = attr.evolve(
                fixed_stored_obj, message=b"\n" + fixed_stored_obj.message,
            )
            if fixed_stored_obj.compute_hash() == obj_id:
                write_fixed_object(swhid, fixed_stored_obj)
                return "fixable_leading_newlines"

    # Try some hardcoded fullname susbstitutions
    substitutions = {
        b"name <email>": b" name  < email >",
        b"unknown <Cl\xc3\xa9ment@.(none)>": b"unknown <Cl\xe9ment@.(none)>",
        b"unknown <J\xef\xbf\xbdrgen@Aspire.(none)>": b"unknown <J\xfcrgen@Aspire.(none)>",
        b"from site <kevoree@kevoree.org>": b" from site  < kevoree@kevoree.org >",
        b" <>": b"",
    }
    fixed_stored_obj = attr.evolve(
        stored_obj,
        author=attr.evolve(
            stored_obj.author,
            fullname=substitutions.get(
                stored_obj.author.fullname, stored_obj.author.fullname
            ),
        ),
        committer=attr.evolve(
            stored_obj.committer,
            fullname=substitutions.get(
                stored_obj.committer.fullname, stored_obj.committer.fullname
            ),
        ),
    )
    if fixed_stored_obj.compute_hash() == obj_id:
        write_fixed_object(swhid, fixed_stored_obj)
        return "fixable_author_hardcoded"
    if fixed_stored_obj.author.fullname == b"unknown <Cl\xe9ment@.(none)>":
        fixed_stored_obj = attr.evolve(
            fixed_stored_obj,
            extra_headers=(
                *fixed_stored_obj.extra_headers,
                (b"encoding", b"ISO-8859-1"),
            ),
        )
        if fixed_stored_obj.compute_hash() == obj_id:
            write_fixed_object(swhid, fixed_stored_obj)
            return "fixable_author_and_encoding_hardcoded"

    # Try removing leading space:
    author = stored_obj.author
    committer = stored_obj.committer
    if author.fullname.startswith(b" "):
        author = attr.evolve(author, fullname=author.fullname[1:])
    if committer.fullname.startswith(b" "):
        committer = attr.evolve(committer, fullname=committer.fullname[1:])
    fixed_stored_obj = attr.evolve(stored_obj, author=author, committer=committer)
    if fixed_stored_obj.compute_hash() == obj_id:
        write_fixed_object(swhid, fixed_stored_obj)
        return "fixable_author_fullname_strip_leading_space"

    # When the fullname is in both the name and the email
    # have: xxx<yyy@zzz> <xxx <yyy@zzz>>
    # want: xxx<yyy@zzz> <xxx<yyy@zzz>>
    author = stored_obj.author
    committer = stored_obj.committer
    if author.name and author.email and b">" in author.name and b">" in author.email:
        author = attr.evolve(
            author,
            fullname=b"<".join(author.fullname.rsplit(b" <", 1)),  # replace last occur
        )
    if (
        committer.name
        and committer.email
        and b">" in committer.name
        and b">" in committer.email
    ):
        committer = attr.evolve(
            committer, fullname=b"<".join(committer.fullname.rsplit(b" <", 1)),  # ditto
        )
    fixed_stored_obj = attr.evolve(stored_obj, author=author, committer=committer)
    if fixed_stored_obj.compute_hash() == obj_id:
        write_fixed_object(swhid, fixed_stored_obj)
        return "fixable_author_fullname_in_name_and_email"

    if (
        stored_obj.date.offset == stored_obj.committer_date.offset == 0
        and stored_obj.author.fullname.startswith(b" ")
    ):
        fixed_stored_obj = attr.evolve(
            stored_obj,
            author=attr.evolve(
                stored_obj.author, fullname=stored_obj.author.fullname[1:]
            ),
            committer=attr.evolve(
                stored_obj.committer, fullname=stored_obj.committer.fullname[1:]
            ),
            date=attr.evolve(stored_obj.date, negative_utc=True),
            committer_date=attr.evolve(stored_obj.committer_date, negative_utc=True),
        )
        if fixed_stored_obj.compute_hash() == obj_id:
            write_fixed_object(swhid, fixed_stored_obj)
            return f"fixable_space_and_negative_utc"

        fixed_stored_obj = attr.evolve(
            fixed_stored_obj, message=(stored_obj.message or b"") + b"\n",
        )
        if fixed_stored_obj.compute_hash() == obj_id:
            write_fixed_object(swhid, fixed_stored_obj)
            return f"fixable_space_and_newline_and_negative_utc"

    # Try capitalizing the 'parent' revision
    stored_manifest_lines = stored_manifest.split(b"\n")
    fixed_stored_manifest_lines = [
        b"parent " + line.split(b" ")[1].upper()
        if line.startswith(b"parent ")
        else line
        for line in stored_manifest_lines
    ]
    fixed_stored_manifest = b"\n".join(fixed_stored_manifest_lines)
    if hashlib.new("sha1", fixed_stored_manifest).digest() == obj_id:
        write_fixed_manifest(swhid, fixed_stored_manifest)
        return "weird_capitalized_revision_parent"

    # Try removing leading zero in date offsets (very crude...)
    stored_manifest_lines = stored_manifest.split(b"\n")
    for (unpad_author, unpad_committer) in [(0, 1), (1, 0), (1, 1)]:
        fixed_stored_manifest_lines = list(stored_manifest_lines)
        if unpad_author:
            fixed_stored_manifest_lines = [
                re.sub(br"([+-])0", lambda m: m.group(1), line)
                if line.startswith(b"author ")
                else line
                for line in fixed_stored_manifest_lines
            ]
        if unpad_committer:
            fixed_stored_manifest_lines = [
                re.sub(br"([+-])0", lambda m: m.group(1), line)
                if line.startswith(b"committer ")
                else line
                for line in fixed_stored_manifest_lines
            ]
        fixed_stored_manifest = b"\n".join(fixed_stored_manifest_lines)
        object_header, rest = fixed_stored_manifest.split(b"\x00", 1)
        fixed_stored_manifest = b"commit " + str(len(rest)).encode() + b"\x00" + rest
        if hashlib.new("sha1", fixed_stored_manifest).digest() == obj_id:
            write_fixed_manifest(swhid, fixed_stored_manifest)
            return f"weird-unpadded_time_offset"

    if stored_obj.date.offset == stored_obj.committer_date.offset == (6 * 60 + 15):
        fixed_stored_manifest = stored_manifest.replace(b"+0615", b"+0575")
        if hashlib.new("sha1", fixed_stored_manifest).digest() == obj_id:
            write_fixed_manifest(swhid, fixed_stored_manifest)
            return "weird-offset=+0575"

    if stored_obj.date.offset == stored_obj.committer_date.offset == (7 * 60 + 0):
        fixed_stored_manifest = stored_manifest.replace(b"+0700", b"--700")
        if hashlib.new("sha1", fixed_stored_manifest).digest() == obj_id:
            write_fixed_manifest(swhid, fixed_stored_manifest)
            return "weird-offset=--700"

    for offset in (
        b"-041800",
        b"-12257",
        b"-12255",
        b"-72000",
        b"-12242",
        b"-12310",
        b"-3600",
        b"-1900",
        b"0000",
        b"+0575",
        b"+041800",
        b"+051800",
        b"+091800",
        b"+1073603",
        b"+1558601",
        b"+1558010",
        b"+1559432",
        b"+1670119",
        b"+15094352",
        b"+15094728",
        b"+27455236",
        b"+40347417",
    ):
        fixed_stored_manifest = stored_manifest.replace(
            b" +0000", b" " + offset
        ).replace(b"+51800", offset)
        object_header, rest = fixed_stored_manifest.split(b"\x00", 1)
        fixed_stored_manifest = b"commit " + str(len(rest)).encode() + b"\x00" + rest
        if hashlib.new("sha1", fixed_stored_manifest).digest() == obj_id:
            write_fixed_manifest(swhid, fixed_stored_manifest)
            return f"weird-offset-misc"

    # Try replacing +0002 with +02
    if stored_obj.date.offset == 2 or stored_obj.committer_date.offset == 2:
        for (unpad_author, unpad_committer) in ((0, 1), (1, 0), (1, 1)):
            fixed_stored_manifest = b"\n".join(
                line.replace(b" +0002", b" +02")
                if (unpad_author and line.startswith(b"author "))
                or (unpad_committer and line.startswith(b"committer "))
                else line
                for line in stored_manifest.split(b"\n")
            )
            (*_, rest) = fixed_stored_manifest.split(b"\x00", 1)
            fixed_stored_manifest = (
                b"commit " + str(len(rest)).encode() + b"\x00" + rest
            )
            if hashlib.new("sha1", fixed_stored_manifest).digest() == obj_id:
                write_fixed_manifest(swhid, fixed_stored_manifest)
                return f"weird-offset={offset.decode()}"
            if fixed_stored_manifest.endswith(b"\n"):
                fixed_stored_manifest = fixed_stored_manifest.rstrip()
                (*_, rest) = fixed_stored_manifest.split(b"\x00", 1)
                fixed_stored_manifest = (
                    b"commit " + str(len(rest)).encode() + b"\x00" + rest
                )
                if hashlib.new("sha1", fixed_stored_manifest).digest() == obj_id:
                    write_fixed_manifest(swhid, fixed_stored_manifest)
                    return f"weird-offset={offset.decode()}"

    # If the timezone is 0, try some other ones
    offsets = {i * 60 + (+1 if i >= 0 else -1) * 59 for i in range(-12, 13)} | {
        -22 * 60 - 0,
        0,
        12 * 60 + 0,
        14 * 60 + 0,
        20 * 60 + 0,
        80 * 60 + 0,
        stored_obj.committer_date.offset,
        stored_obj.date.offset,
    }
    for committer_offset in (
        offsets
        if stored_obj.committer_date.offset == 0
        else [stored_obj.committer_date.offset]
    ):
        for author_offset in (
            offsets if stored_obj.date.offset == 0 else [stored_obj.date.offset]
        ):
            fixed_stored_obj = attr.evolve(
                stored_obj,
                date=attr.evolve(
                    stored_obj.date, offset=author_offset, negative_utc=False
                ),
                committer_date=attr.evolve(
                    stored_obj.committer_date,
                    offset=committer_offset,
                    negative_utc=False,
                ),
            )
            if fixed_stored_obj.compute_hash() == obj_id:
                write_fixed_object(swhid, fixed_stored_obj)
                return "fixable_offset"
            fixed_stored_obj = attr.evolve(
                fixed_stored_obj, message=b"\n" + (fixed_stored_obj.message or b"")
            )
            if fixed_stored_obj.compute_hash() == obj_id:
                write_fixed_object(swhid, fixed_stored_obj)
                return "fixable_offset_and_newline"

    return None


def try_fix_release(swhid, stored_obj, stored_manifest):
    obj_id = swhid.object_id

    # Try nullifying a zero date
    if stored_obj.date is not None and stored_obj.date.timestamp.seconds == 0:
        fixed_stored_obj = attr.evolve(stored_obj, date=None,)
        if fixed_stored_obj.compute_hash() == obj_id:
            write_fixed_object(swhid, fixed_stored_obj)
            return "fixable_nullify_zero_date"

    # Try zeroing a null date
    if stored_obj.date is None:
        fixed_stored_obj = attr.evolve(stored_obj, date=ZERO_TIMESTAMP)
        if fixed_stored_obj.compute_hash() == obj_id:
            write_fixed_object(swhid, fixed_stored_obj)
            return "fixable_zero_null_date"

    return None


def directory_with_custom_sort(directory, key):
    """Like swh.model.git_objects.directory_git_object, but does not sort entries."""
    components = []

    for entry in sorted(directory.entries, key=key):
        components.extend(
            [_perms_to_bytes(entry.perms), b"\x20", entry.name, b"\x00", entry.target,]
        )
    fixed_manifest = format_git_object_from_parts("tree", components)
    return (fixed_manifest, hashlib.new("sha1", fixed_manifest).hexdigest())


def directory_identifier_with_no_sort(directory):
    """Like swh.model.git_objects.directory_git_object, but does not sort entries."""
    components = []

    for entry in directory.entries:
        components.extend(
            [_perms_to_bytes(entry.perms), b"\x20", entry.name, b"\x00", entry.target,]
        )
    git_object = format_git_object_from_parts("tree", components)
    return hashlib.new("sha1", git_object).hexdigest()


def try_fix_directory(swhid, stored_obj, stored_manifest):
    obj_id = swhid.object_id

    possible_rewrites = [
        (0o40000, 0o40755),
        (0o40000, 0o40775),
        (0o40000, 0o40777),
        (0o100755, 0o100744),
        (0o100755, 0o100775),
        (0o100755, 0o100777),
        (0o100644, 0o100664),
        (0o100644, 0o100666),
    ]

    assert stored_obj.compute_hash() != stored_obj.id

    for nb_rewrites in range(1, len(possible_rewrites) + 1):
        for rewrite in itertools.combinations(possible_rewrites, nb_rewrites):
            rewrite_dict = dict(rewrite)
            fixed_entries = tuple(
                attr.evolve(entry, perms=rewrite_dict.get(entry.perms, entry.perms))
                for entry in stored_obj.entries
            )
            fixed_obj = attr.evolve(stored_obj, entries=fixed_entries)
            if fixed_obj == stored_obj:
                # pointless to recompute the hash
                continue
            if fixed_obj.compute_hash() == stored_obj.id:
                write_fixed_object(swhid, fixed_obj)
                return "fixable_directory_perms"

    fixed_stored_manifest = stored_manifest.replace(b"40000 ", b"040000 ")
    (*_, rest) = fixed_stored_manifest.split(b"\x00", 1)
    fixed_stored_manifest = b"tree " + str(len(rest)).encode() + b"\x00" + rest
    if hashlib.new("sha1", fixed_stored_manifest).digest() == obj_id:
        write_fixed_manifest(swhid, fixed_stored_manifest)
        return f"weird-padded_perms_40000"

    (fixed_stored_manifest, fixed_id) = directory_with_custom_sort(stored_obj, key=lambda entry: entry.name)
    if fixed_id == stored_obj.id.hex():
        write_fixed_manifest(swhid, fixed_stored_manifest)
        return f"weird-dir_with_nullbyte_sort"

    (fixed_stored_manifest, fixed_id) = directory_with_custom_sort(
            stored_obj, key=lambda entry: ["file", "dir", "rev"].index(entry.type)
        )
    if fixed_id == stored_obj.id.hex():
        write_fixed_manifest(swhid, fixed_stored_manifest)
        return f"weird-dir_with_filefirst_partial_sort"

    (fixed_stored_manifest, fixed_id) = directory_with_custom_sort(
            stored_obj,
            key=lambda entry: (
                ["file", "dir", "rev"].index(entry.type),
                directory_entry_sort_key(entry),
            ),
        )
    if fixed_id == stored_obj.id.hex():
        write_fixed_manifest(swhid, fixed_stored_manifest)
        return f"weird-dir_with_filefirst_full_git_sort"

    (fixed_stored_manifest, fixed_id) = directory_with_custom_sort(
            stored_obj,
            key=lambda entry: (["file", "dir", "rev"].index(entry.type), entry.name),
        )
    if fixed_id == stored_obj.id.hex():
        write_fixed_manifest(swhid, fixed_stored_manifest)
        return f"weird-dir_with_filefirst_full_nullbyte_sort"

    (fixed_stored_manifest, fixed_id) = directory_with_custom_sort(
            stored_obj, key=lambda entry: ["dir", "file", "rev"].index(entry.type)
        )
    if fixed_id == stored_obj.id.hex():
        write_fixed_manifest(swhid, fixed_stored_manifest)
        return f"weird-dir_with_dirfirst_partial_sort"

    (fixed_stored_manifest, fixed_id) = directory_with_custom_sort(
            stored_obj,
            key=lambda entry: (
                ["dir", "file", "rev"].index(entry.type),
                directory_entry_sort_key(entry),
            ),
        )
    if fixed_id == stored_obj.id.hex():
        write_fixed_manifest(swhid, fixed_stored_manifest)
        return f"weird-dir_with_dirfirst_full_git_sort"

    (fixed_stored_manifest, fixed_id) = directory_with_custom_sort(
            stored_obj,
            key=lambda entry: (["dir", "file", "rev"].index(entry.type), entry.name),
        )
    if fixed_id == stored_obj.id.hex():
        write_fixed_manifest(swhid, fixed_stored_manifest)
        return f"weird-dir_with_dirfirst_full_nullbyte_sort"

    (fixed_stored_manifest, fixed_id) = directory_with_custom_sort(stored_obj, key=lambda entry: ())
    if fixed_id == stored_obj.id.hex():
        write_fixed_manifest(swhid, fixed_stored_manifest)
        return f"weird-dir_with_pg_order"

    # Replace '40000' with '040000' for all entries *but one*.
    # There is a surprisingly large number of dirs where this is the issue!
    parts = stored_manifest.split(b"40000 ")
    for i in range(len(parts)):
        fixed_stored_manifest = (
            b"040000 ".join(parts[0 : i + 1])
            + b"40000 "
            + b"040000 ".join(parts[i + 1 :])
        )
        (*_, rest) = fixed_stored_manifest.split(b"\x00", 1)
        fixed_stored_manifest = b"tree " + str(len(rest)).encode() + b"\x00" + rest
        if hashlib.new("sha1", fixed_stored_manifest).digest() == obj_id:
            write_fixed_manifest(swhid, fixed_stored_manifest)
            return f"weird-padded_perms_40000_except_1"

    return None


def get_origins(swhid, stored_obj):
    obj_id = swhid.object_id

    storage = get_storage(
        "pipeline",
        steps=[
            dict(cls="retry"),
            dict(
                cls="remote", url="http://webapp1.internal.softwareheritage.org:5002/"
            ),
        ],
    )
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
            except GraphArgumentException as e:
                # try again with the local graph (more up to date, but partial)
                try:
                    origin_swhids = [
                        ExtendedSWHID.from_string(line)
                        for line in graph2.leaves(swhid, direction="backward")
                        if line.startswith("swh:1:ori:")
                    ]
                except GraphArgumentException as e:
                    return (
                        False,
                        f"unrecoverable_{swhid.object_type.value}_not-in-swh-graph",
                    )
                except:
                    pass
                else:
                    break
            except:
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


def get_object_from_origins(swhid, stored_obj):
    obj_id = swhid.object_id
    (success, res) = get_origins(swhid, stored_obj)
    if not success:
        return (False, res)
    origins = res
    for origin_url in origins:
        if not origin_url.endswith(".git"):
            origin_url += ".git"
        if origin_url == "https://github.com/reingart/python.git":
            # Fails very often...
            continue

        data = b"0032want " + hash_to_bytehex(obj_id) + b"\n"
        if swhid.object_type == ObjectType.REVISION:
            for parent in stored_obj.parents:
                data += b"0032have " + hash_to_bytehex(parent) + b"\n"
        elif swhid.object_type == ObjectType.RELEASE:
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
        return (False, f"unrecoverable_{swhid.object_type.value}_no-origin")

    return (True, origin_url, cloned_obj)


def try_recover_revision(
    swhid, stored_obj, stored_manifest, cloned_obj, cloned_manifest, origin_url
):
    obj_id = swhid.object_id
    fixed_stored_obj = stored_obj

    # Try adding gpgsig
    if (
        b"gpgsig" not in dict(stored_obj.extra_headers)
        and cloned_obj.gpgsig is not None
    ):
        fixed_stored_obj = attr.evolve(
            stored_obj,
            extra_headers=(
                *[(k, v) for (k, v) in stored_obj.extra_headers if k != b"nonce"],
                (b"gpgsig", cloned_obj.gpgsig),
                *[(k, v) for (k, v) in stored_obj.extra_headers if k == b"nonce"],
            ),
        )
        if fixed_stored_obj.compute_hash() == obj_id:
            write_fixed_object(swhid, fixed_stored_obj)
            return "recoverable_missing_gpgsig"

    # Try adding mergetag (on top of gpgsig)
    if (
        b"mergetag" not in dict(stored_obj.extra_headers)
        and cloned_obj.mergetag is not None
    ):
        # fixed_stored_obj = stored_obj  # commented out to reuse the gpgsig-fixed
        mergetags = []
        for mergetag in cloned_obj.mergetag:
            mergetag = mergetag.as_raw_string()
            assert mergetag.endswith(b"\n")
            mergetags.append((b"mergetag", mergetag[0:-1]))
        fixed_stored_obj = attr.evolve(
            fixed_stored_obj, extra_headers=(*mergetags, *stored_obj.extra_headers,),
        )
        if fixed_stored_obj.compute_hash() == obj_id:
            write_fixed_object(swhid, fixed_stored_obj)
            return "recoverable_missing_mergetag_and_maybe_gpgsig"

    # Try adding a magic string at the end of the message
    if stored_obj.message and stored_obj.message.endswith(b"--HG--\nbranch : "):
        # Probably https://github.com/GWBasic/ObjectCloud.git
        assert cloned_obj.message.startswith(stored_obj.message)
        fixed_stored_obj = attr.evolve(stored_obj, message=cloned_obj.message)
        if fixed_stored_obj.compute_hash() == obj_id:
            write_fixed_object(swhid, fixed_stored_obj)
            return "recoverable_hg_branch_nullbytes_truncated"

    # Try copying extra headers (including gpgsig)
    extra_headers = cloned_obj.extra
    if cloned_obj.gpgsig is not None:
        extra_headers = (*extra_headers, (b"gpgsig", cloned_obj.gpgsig))
    fixed_stored_obj = attr.evolve(stored_obj, extra_headers=extra_headers)
    if fixed_stored_obj.compute_hash() == obj_id:
        write_fixed_object(swhid, fixed_stored_obj)
        return "recoverable_extra_headers"
    if {b"HG:extra", b"HG:rename-source", b"HG:rename"} & set(dict(extra_headers)):
        for n in range(4):
            fixed_stored_obj = attr.evolve(
                fixed_stored_obj, message=b"\n" + fixed_stored_obj.message
            )
            if fixed_stored_obj.compute_hash() == obj_id:
                write_fixed_object(swhid, fixed_stored_obj)
                return "recoverable_extra_headers_and_leading_newlines"

    print("=" * 100)
    print("Failed to fix:")
    print("origin_url", origin_url)
    print("original", repr(cloned_manifest.split(b"\x00", 1)[1]))
    print("stored  ", repr(stored_manifest.split(b"\x00", 1)[1]))
    print(
        "\n".join(
            difflib.ndiff(
                cloned_manifest.split(b"\x00", 1)[1]
                .decode(errors="backslashreplace")
                .split("\n"),
                stored_manifest.split(b"\x00", 1)[1]
                .decode(errors="backslashreplace")
                .split("\n"),
            )
        )
    )
    print("=" * 100)

    return None


def try_recover_release(
    swhid, stored_obj, stored_manifest, cloned_obj, cloned_manifest, origin_url
):
    obj_id = swhid.object_id

    if cloned_obj.signature is not None:
        fixed_stored_obj = attr.evolve(
            stored_obj, message=(stored_obj.message or b"") + cloned_obj.signature
        )
        if fixed_stored_obj.compute_hash() == obj_id:
            write_fixed_object(swhid, fixed_stored_obj)
            return "recoverable_missing_gpgsig"

    if cloned_obj.signature is not None:
        fixed_stored_obj = attr.evolve(
            stored_obj,
            date=ZERO_TIMESTAMP,
            message=(stored_obj.message or b"") + cloned_obj.signature,
        )
        if fixed_stored_obj.compute_hash() == obj_id:
            write_fixed_object(swhid, fixed_stored_obj)
            return "recoverable_missing_gpgsig_and_zero_date"

    print("original", repr(cloned_manifest.split(b"\x00", 1)[1]))
    print("stored  ", repr(stored_manifest.split(b"\x00", 1)[1]))
    print(
        "\n".join(
            difflib.ndiff(
                cloned_manifest.split(b"\x00", 1)[1]
                .decode(errors="backslashreplace")
                .split("\n"),
                stored_manifest.split(b"\x00", 1)[1]
                .decode(errors="backslashreplace")
                .split("\n"),
            )
        )
    )


def try_recover_directory(
    swhid, stored_obj, stored_manifest, cloned_obj, cloned_manifest, origin_url
):
    obj_id = swhid.object_id

    print("original", repr(cloned_manifest.split(b"\x00", 1)[1]))

    if stored_manifest is not None:
        print("stored  ", repr(stored_manifest.split(b"\x00", 1)[1]))
        print(
            "\n".join(
                difflib.ndiff(
                    [
                        repr(entry)
                        for entry in re.findall(
                            b"[0-9]+ [^\x00]+\x00.{20}",
                            cloned_manifest.split(b"\x00", 1)[1],
                        )
                    ],
                    [
                        repr(entry)
                        for entry in re.findall(
                            b"[0-9]+ [^\x00]+\x00.{20}",
                            stored_manifest.split(b"\x00", 1)[1],
                        )
                    ],
                )
            )
        )


def handle_pdb(sig, frame):
    import pdb

    pdb.Pdb().set_trace(frame)


if __name__ == "__main__":
    signal.signal(signal.SIGUSR1, handle_pdb)
    main(sys.stdin)
