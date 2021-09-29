import collections
import difflib
import hashlib
import multiprocessing.dummy
import pathlib
import re
import socket
import ssl
import subprocess
import sys
import tempfile
import traceback
import urllib.parse

import attr
import dulwich.client
import dulwich.errors
import dulwich.object_store
import dulwich.pack
import dulwich.repo
import requests
import tqdm

from swh.core.utils import grouper
from swh.graph.client import RemoteGraphClient, GraphArgumentException
from swh.model.hashutil import hash_to_bytes, hash_to_hex, hash_to_bytehex
from swh.model.git_objects import directory_git_object, revision_git_object
from swh.model.model import Directory, Origin, Person, RevisionType
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
    r"Fixable (?P<obj_type>[a-z]+) (?P<obj_id>[0-9a-f]{40}) \((?P<how>.*)\)"
)
UNORDERED_DIRECTORY = re.compile(
    r"Weird directory checksum (?P<obj_id>[0-9a-f]{40}) \(computed without sorting\)"
)
NOISE = re.compile(r"Called Ctrl-C\, exiting\.")

ENCODINGS = (
    b"SHIFT_JIS",
    b"Shift-JIS",
    b"iso8859-1",
    b"iso-8859-1",
    b"ISO-8859-1",
    b" ISO-8859-1",
    b"iso8859-15",
    b"UTF8]",  # sic
    b"UTF-8 UTF8",
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
    b"ru_RU.KOI8-R",
    b"cp1250",
    b"CP-1252",
    b"cp-1251",
    b"cp932",
    b"latin-1",
    b"Latin-1",
    b"ISO-2022-JP",
    b"KOI8-R",
    b"windows-1252",
    b"euckr",
    b"ISO-88592",
    b"iso10646-1",
    b"iso-8859-7",
    b"=",
    b"CP950",
    b"win",
)


storage = get_storage(
    "remote", url="http://webapp1.internal.softwareheritage.org:5002/"
)
graph = RemoteGraphClient("http://graph.internal.softwareheritage.org:5009/graph/")


REVISIONS = {}


def get_clone_path(origin_url):
    origin_id = Origin(url=origin_url).swhid()
    dirname = f"{origin_id}_{origin_url.replace('/', '_')}"
    return CLONES_BASE_DIR / dirname


def clone(origin_url):
    clone_path = get_clone_path(origin_url)
    if clone_path.is_dir():
        # already cloned
        return
    # print("Cloning", origin_url)
    subprocess.run(
        ["git", "clone", "--bare", origin_url, clone_path],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def get_object_from_clone(origin_url, obj_id):
    clone_path = get_clone_path(origin_url)
    repo = dulwich.repo.Repo(str(clone_path))
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
    return dict(zip(ids, storage.revision_get(ids)))


def main(input_fd):
    digest = collections.defaultdict(set)

    # Parse logs from check_consistency.py to 'digest'
    for line in tqdm.tqdm(
        list(input_fd), desc="parsing input", unit="line", unit_scale=True
    ):
        handle_line(digest, line)

    # preload revisions in batches
    revision_id_groups = list(grouper(digest["mismatch_misc_revision"], 1000))[0:200]
    # revision_id_groups = list(grouper(digest["mismatch_hg_to_git"], 1000))
    # revision_id_groups = list(
    #    grouper(digest["mismatch_misc_revision"] | digest["mismatch_hg_to_git"], 1000)
    # )
    with multiprocessing.dummy.Pool(10) as p:
        for revisions in tqdm.tqdm(
            p.imap_unordered(_load_revisions, revision_id_groups),
            desc="loading revisions",
            unit="k revs",
            total=len(revision_id_groups),
        ):
            REVISIONS.update(revisions)

    def f(obj_id):
        return (obj_id, try_recovery(digest, ObjectType.REVISION, obj_id))

    # Try to fix objects one by one
    with multiprocessing.dummy.Pool(16) as p:
        for key in ("mismatch_misc_revision",):
            # for key in ("mismatch_hg_to_git",):
            # for key in ("mismatch_misc_revision", "mismatch_hg_to_git",):
            unrecoverable = set()
            for (obj_id, is_recoverable) in tqdm.tqdm(
                p.imap_unordered(f, digest[key]),
                desc=f"recovering {key}",
                unit="rev",
                total=len(digest[key]),
                smoothing=0.01,
            ):
                if not is_recoverable:
                    unrecoverable.add(obj_id)
            digest[key] = unrecoverable

    for (type_, obj_ids) in sorted(digest.items()):
        print(f"{(type_ + ':'):20} {len(obj_ids)}")


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
        digest["mismatch_svn"].add(hash_to_bytes(m.group("obj_id")))
        return
    m = FIXABLE.fullmatch(line)
    if m:
        digest["fixable"].add(hash_to_bytes(m.group("obj_id")))
        return
    m = UNORDERED_DIRECTORY.fullmatch(line)
    if m:
        digest["unordered_dir"].add(hash_to_bytes(m.group("obj_id")))
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


def try_recovery(digest, obj_type, obj_id):
    """Try fixing the given obj_id. If successful, adds it to the digest and returns
    True. Otherwise, returns False."""
    obj_id = hash_to_bytes(obj_id)
    swhid = CoreSWHID(object_type=obj_type, object_id=obj_id)

    if obj_type == ObjectType.REVISION:
        stored_obj = REVISIONS[obj_id]
        if stored_obj is None:
            digest["revision_missing_from_storage"].add(obj_id)
            return True
        if stored_obj.type != RevisionType.GIT:
            digest[f"mismatch_misc_revision_{stored_obj.type.value}"].add(obj_id)
            print(f"skipping {swhid}, type: {stored_obj.type.value}")
            return True
        stored_manifest = revision_git_object(stored_obj)
    elif obj_type == ObjectType.DIRECTORY:
        stored_obj = Directory(
            id=obj_id,
            entries=list(
                stream_results_optional(storage.directory_get_entries, obj_id)
            ),
        )
        stored_manifest = revision_git_object(stored_obj)
    else:
        assert False, obj_type

    assert obj_id == stored_obj.id
    assert obj_id != stored_obj.compute_hash(), "Hash matches this time?!"

    # Try adding spaces in the name
    # eg. https://github.com/ekam/Zurmo
    for committer_only in (True, False):
        for padding in (1, 2, 4, 5, 8):
            fullname = stored_obj.author.fullname.replace(
                b" <", b" " + b" " * padding + b"<"
            )
            fixed_stored_obj = attr.evolve(
                stored_obj,
                author=stored_obj.author
                if committer_only
                else Person(fullname=fullname, name=b"", email=b""),
                committer=Person(fullname=fullname, name=b"", email=b""),
            )
            if fixed_stored_obj.compute_hash() == obj_id:
                digest["fixable_author_middle_spaces"].add(obj_id)
                return True

    # Try adding leading space to email
    # (very crude, this assumes author = committer)
    fullname = stored_obj.author.fullname.replace(b" <", b" < ")
    fixed_stored_obj = attr.evolve(
        stored_obj,
        author=Person(fullname=fullname, name=b"", email=b""),
        committer=Person(fullname=fullname, name=b"", email=b""),
    )
    if fixed_stored_obj.compute_hash() == obj_id:
        digest["fixable_author_email_leading_space"].add(obj_id)
        return True

    # Try adding trailing space to email
    # (very crude, this assumes author = committer)
    fullname = stored_obj.author.fullname[0:-1] + b" >"
    fixed_stored_obj = attr.evolve(
        stored_obj,
        author=Person(fullname=fullname, name=b"", email=b""),
        committer=Person(fullname=fullname, name=b"", email=b""),
    )
    if fixed_stored_obj.compute_hash() == obj_id:
        digest["fixable_author_email_trailing_space"].add(obj_id)
        return True

    # Try adding spaces before the name
    fullname = b" " + stored_obj.author.fullname
    fixed_stored_obj = attr.evolve(
        stored_obj,
        author=Person(fullname=fullname, name=b"", email=b""),
        committer=Person(fullname=fullname, name=b"", email=b""),
    )
    if fixed_stored_obj.compute_hash() == obj_id:
        digest["fixable_author_leading_space"].add(obj_id)
        return True

    # Try adding spaces after the name
    if stored_obj.author.fullname.endswith(b"samba.org>"):
        fullname = stored_obj.author.fullname + b" "
        fixed_stored_obj = attr.evolve(
            stored_obj,
            author=Person(fullname=fullname, name=b"", email=b""),
            committer=Person(fullname=fullname, name=b"", email=b""),
        )
        if fixed_stored_obj.compute_hash() == obj_id:
            digest["fixable_author_trailing_space"].add(obj_id)
            return True
        fixed_stored_obj = attr.evolve(
            fixed_stored_obj, message=b"\n" + fixed_stored_obj.message
        )
        if fixed_stored_obj.compute_hash() == obj_id:
            digest["fixable_author_trailing_space_and_leading_newline"].add(obj_id)
            return True

    # Try adding leading newlines
    if stored_obj.message is not None:
        fixed_stored_obj = stored_obj
        for _ in range(4):
            fixed_stored_obj = attr.evolve(
                fixed_stored_obj, message=b"\n" + fixed_stored_obj.message,
            )
            if fixed_stored_obj.compute_hash() == obj_id:
                digest["leading_newlines"].add(obj_id)
                return True

    # If the timezone is 0, try some other ones
    offsets = {
        0,
        0 * 60 + 59,
        1 * 60 + 59,
        3 * 60 + 59,
        8 * 60 + 59,
        12 * 60 + 0,
        14 * 60 + 0,
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
                date=attr.evolve(stored_obj.date, offset=author_offset),
                committer_date=attr.evolve(
                    stored_obj.committer_date, offset=committer_offset
                ),
            )
            if fixed_stored_obj.compute_hash() == obj_id:
                digest["fixable_offset"].add(obj_id)
                return True

    if stored_obj.date.offset == stored_obj.committer_date.offset == (7 * 60 + 0):
        fixed_stored_manifest = stored_manifest.replace(b"+0700", b"--700")
        if hashlib.new("sha1", fixed_stored_manifest).digest() == obj_id:
            digest["weird-offset--700"].add(obj_id)
            return True

    # Try adding an encoding header
    if b"encoding" not in dict(stored_obj.extra_headers):
        for encoding in ENCODINGS:
            fixed_stored_obj = attr.evolve(
                stored_obj,
                extra_headers=(*stored_obj.extra_headers, (b"encoding", encoding)),
            )
            if fixed_stored_obj.compute_hash() == obj_id:
                digest[f"fixable_add_encoding_{encoding}"].add(obj_id)
                return True
            if fixed_stored_obj.message is not None:
                for _ in range(3):
                    fixed_stored_obj = attr.evolve(
                        fixed_stored_obj, message=b"\n" + fixed_stored_obj.message,
                    )
                    if fixed_stored_obj.compute_hash() == obj_id:
                        digest[
                            f"fixable_add_encoding_{encoding}_and_leading_newlines"
                        ].add(obj_id)
                        return True

    # Try removing leading zero in date offsets (very crude...)
    stored_manifest_lines = stored_manifest.split(b"\n")
    for (unpad_author, unpad_committer) in [(0, 1), (1, 0), (1, 1)]:
        fixed_manifest_lines = list(stored_manifest_lines)
        if unpad_author:
            fixed_manifest_lines = [
                re.sub(br"([+-])0", lambda m: m.group(1), line)
                if line.startswith(b"author ")
                else line
                for line in fixed_manifest_lines
            ]
        if unpad_committer:
            fixed_manifest_lines = [
                re.sub(br"([+-])0", lambda m: m.group(1), line)
                if line.startswith(b"committer ")
                else line
                for line in fixed_manifest_lines
            ]
        fixed_stored_manifest = b"\n".join(fixed_manifest_lines)
        object_header, rest = fixed_stored_manifest.split(b"\x00", 1)
        fixed_stored_manifest = b"commit " + str(len(rest)).encode() + b"\x00" + rest
        if hashlib.new("sha1", fixed_stored_manifest).digest() == obj_id:
            digest["unpadded_time_offset_{unpad_author}_{unpad_committer}"].add(obj_id)
            return True

    for _ in range(10):
        try:
            origin_swhids = [
                ExtendedSWHID.from_string(line)
                for line in graph.leaves(swhid, direction="backward")
                if line.startswith("swh:1:ori:")
            ]
        except GraphArgumentException:
            print(f"{swhid} not available in swh-graph")
            return False
        except:
            pass
        else:
            break
    else:
        print(f"swh-graph keeps error while fetching origins for {swhid}, giving up.")
        return False
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

    for origin_url in origins:
        if not origin_url.endswith(".git"):
            origin_url += ".git"
        if origin_url == "https://github.com/reingart/python.git":
            # Fails very often...
            continue

        data = b"0032want " + hash_to_bytehex(obj_id) + b"\n"
        for parent in stored_obj.parents:
            data += b"0032have " + hash_to_bytehex(parent) + b"\n"
        data += b"0000"
        data += b"0009done\n"

        clone_path = get_clone_path(origin_url)
        if not clone_path.is_dir():
            # First, check if we can access the origin and if it still has the
            # commit we want.

            parsed_url = urllib.parse.urlparse(origin_url)
            if parsed_url.scheme == "git":
                # TODO: use the dumb git proto to check?
                try:
                    clone(origin_url)
                except subprocess.CalledProcessError:
                    continue
            elif parsed_url.scheme in ("http", "https"):
                # This is silly, but neither requests or dulwich properly handle
                # some connection terminations for some reason, so we need
                # this home-made HTTP client
                hostname = parsed_url.netloc
                context = ssl.create_default_context()
                try:
                    with socket.create_connection((hostname, 443)) as sock:
                        with context.wrap_socket(
                            sock, server_hostname=hostname
                        ) as ssock:
                            ssock.write(
                                b"POST "
                                + parsed_url.path.encode()
                                + b"/git-upload-pack HTTP/1.0\r\n"
                            )
                            ssock.write(b"Host: " + hostname.encode() + b"\r\n")
                            ssock.write(
                                b"Content-Type: application/x-git-upload-pack-request\r\n"
                            )
                            ssock.write(b"\r\n")
                            ssock.write(data)
                            response = b""
                            while True:
                                new_data = ssock.read()
                                if not new_data:
                                    break
                                response += new_data
                except (TimeoutError, socket.gaierror):
                    # Could not connect
                    continue
                (headers, body) = response.split(b"\r\n\r\n", 1)
                (status_line, headers) = headers.split(b"\r\n", 1)
                if b"401" in status_line or b"404" in status_line:
                    # Repo not available
                    continue
                elif any(code in status_line for code in (b"200", b"500", b"302")):
                    # 500 happens on gitlab for some reason
                    try:
                        clone(origin_url)
                    except subprocess.CalledProcessError:
                        continue
                else:
                    assert False, (
                        f"unexpected response when querying {hash_to_hex(obj_id)} "
                        f"on {origin_url}: {status_line}\n{body}"
                    )

        try:
            cloned_obj = get_object_from_clone(origin_url, obj_id)
        except KeyError:
            # try next origin
            continue
        if cloned_obj is None:
            return False
        break
        """
        response = requests.post(
            origin_url + "/git-upload-pack",
            headers={"Content-Type": "application/x-git-upload-pack-request"},
            data=data,
        )
        print(response)
        print(response.content)
        if response.status_code == 401 and response.content == b"Repository not found.":
            continue
        assert response.status_code == 200
        assert response.content != b""
        """

        """
        print(origin_url)
        client, path = dulwich.client.get_transport_and_path(
            origin_url, thin_packs=False
        )
        graph_walker = dulwich.object_store.ObjectStoreGraphWalker(
            {hash_to_bytehex(obj_id)},
            lambda _: []
        )
        def determine_wants(refs):
            print("determine_wants", refs)
            return [hash_to_bytehex(obj_id)]
        for _ in range(2):
            try:
                buf = tempfile.SpooledTemporaryFile()
                def do_pack(data: bytes):
                    buf.write(data)
                result = client.fetch_pack(
                    path,
                    determine_wants,
                    graph_walker,
                    do_pack,
                )
            except dulwich.errors.HangupException:
                print("HangupException, retrying")
                continue
            except dulwich.client.HTTPUnauthorized:
                return False
            else:
                print(result)
                break
        else:
            print("giving up.")
            continue
        buf_len = buf.tell()
        buf.seek(0)
        print(list(dulwich.pack.PackData.from_file(buf, buf_len).iterentries()))
        buf.seek(0)
        for obj in dulwich.pack.PackInflater.for_pack_data(
            dulwich.pack.PackData.from_file(buf, buf_len)
        ):
            assert obj.sha == hash_to_bytehex(obj_id), (obj.sha, hash_to_hex(obj_id))
            print("success!")
            return True
        else:
            assert False
            print("No object?! Trying next origin")
        """
    else:
        return False

    object_header = (
        cloned_obj.type_name + b" " + str(cloned_obj.raw_length()).encode() + b"\x00"
    )
    cloned_manifest = object_header + cloned_obj.as_raw_string()
    rehash = hashlib.sha1(cloned_manifest).digest()
    assert (
        obj_id == rehash
    ), f"Mismatch between origin hash and original object: {obj_id.hex()} != {rehash.hex()}"

    if obj_type == ObjectType.REVISION:
        # Try adding gpgsig
        if (
            b"gpgsig" not in dict(stored_obj.extra_headers)
            and cloned_obj.gpgsig is not None
        ):
            fixed_stored_obj = attr.evolve(
                stored_obj,
                extra_headers=(
                    *stored_obj.extra_headers,
                    (b"gpgsig", cloned_obj.gpgsig),
                ),
            )
            if fixed_stored_obj.compute_hash() == obj_id:
                digest["recoverable_missing_gpgsig"].add(obj_id)
                return True

        # Try adding mergetag
        if (
            b"mergetag" not in dict(stored_obj.extra_headers)
            and cloned_obj.mergetag is not None
        ):
            fixed_stored_obj = stored_obj
            for mergetag in cloned_obj.mergetag:
                mergetag = mergetag.as_raw_string()
                assert mergetag.endswith(b"\n")
                mergetag = mergetag[0:-1]
                fixed_stored_obj = attr.evolve(
                    fixed_stored_obj,
                    extra_headers=(*stored_obj.extra_headers, (b"mergetag", mergetag),),
                )
            if fixed_stored_obj.compute_hash() == obj_id:
                digest["recoverable_missing_mergetag"].add(obj_id)
                return True

        # Try adding a magic string at the end of the message
        if stored_obj.message and stored_obj.message.endswith(b"--HG--\nbranch : "):
            # Probably https://github.com/GWBasic/ObjectCloud.git
            assert cloned_obj.message.startswith(stored_obj.message)
            fixed_stored_obj = attr.evolve(stored_obj, message=cloned_obj.message)
            if fixed_stored_obj.compute_hash() == obj_id:
                digest["recoverable_hg_branch_nullbytes_truncated"].add(obj_id)
                return True

        # Try copying extra headers (including gpgsig)
        extra_headers = cloned_obj.extra
        if cloned_obj.gpgsig is not None:
            extra_headers = (*extra_headers, (b"gpgsig", cloned_obj.gpgsig))
        fixed_stored_obj = attr.evolve(stored_obj, extra_headers=extra_headers)
        if fixed_stored_obj.compute_hash() == obj_id:
            digest["recoverable_extra_headers"].add(obj_id)
            return True
        if {b"HG:extra", b"HG:rename-source"} & set(dict(extra_headers)):
            for n in range(4):
                fixed_stored_obj = attr.evolve(
                    fixed_stored_obj, message=b"\n" + fixed_stored_obj.message
                )
                if fixed_stored_obj.compute_hash() == obj_id:
                    digest["recoverable_extra_headers_and_leading_newlines"].add(obj_id)
                    return True

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


if __name__ == "__main__":
    main(sys.stdin)
