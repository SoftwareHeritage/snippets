import hashlib
import itertools
import os
import pprint
import sys

import attr

import swh.model.identifiers as identifiers
from swh.model.hashutil import bytehex_to_hash, hash_to_bytes
import swh.model.model as model
from swh.model.model import Person


def fixable_revision_mergetag_newline(rev, d):
    """https://forge.softwareheritage.org/T75#69907"""
    extra_headers = dict(rev.extra_headers)
    mergetag = extra_headers.get(b"mergetag")
    if mergetag is not None and mergetag.endswith(b"\n"):
        fixed_mergetag = mergetag[0:-1]
        # Be sure to preserve order
        fixed_extra_headers = [
            (k, fixed_mergetag) if k == b"mergetag" else (k, v)
            for (k, v) in rev.extra_headers
        ]
        fixed_rev = attr.evolve(rev, extra_headers=fixed_extra_headers)
        if rev.id == fixed_rev.compute_hash():
            print(f"Fixable revision {rev.id.hex()} (removed newline from mergetag)")
            return True
        else:
            print("Failed fixable_revision_mergetag_newline", file=sys.stderr)
            return False


def fixable_revision_gpgsig_newline(rev, d):
    """https://forge.softwareheritage.org/T75#69907"""
    extra_headers = dict(rev.extra_headers)
    gpgsig = extra_headers.get(b"gpgsig")
    if gpgsig is not None and not gpgsig.endswith(b"\n"):
        fixed_gpgsig = gpgsig + b"\n"
        # Be sure to preserve order
        fixed_extra_headers = [
            (k, fixed_gpgsig) if k == b"gpgsig" else (k, v)
            for (k, v) in rev.extra_headers
        ]
        fixed_rev = attr.evolve(rev, extra_headers=fixed_extra_headers)
        if rev.id == fixed_rev.compute_hash():
            print(f"Fixable revision {rev.id.hex()} (added newline to gpgsig)")
            return True
        else:
            print("Failed fixable_revision_gpgsig_newline", file=sys.stderr)
            return False


def fixable_revision_gpgsig_indent(rev, d):
    """item 1 on https://forge.softwareheritage.org/T75#70553"""
    extra_headers = dict(rev.extra_headers)
    gpgsig = extra_headers.get(b"gpgsig")
    if gpgsig is not None and not b"\n" in gpgsig:
        # TODO: there may be extra headers before the gpgsif
        fixed_extra_headers = [(b"gpgsig", gpgsig)] + [
            (k, v) for (k, v) in rev.extra_headers if k != b"gpgsig"
        ]
        fixed_rev = attr.evolve(rev, extra_headers=fixed_extra_headers)
        # TODO: also handle https://forge.softwareheritage.org/T75#69907
        if rev.id == fixed_rev.compute_hash():
            print(
                f"Fixable revision {rev.id.hex()} "
                f"(reordered gpgsig before dummy headers)"
            )
            return True
        else:
            print("Failed fixable_revision_gpgsig_indent", file=sys.stderr)
            return False


def fixable_revision_extra_author_space(rev, d):
    """item 4 on https://forge.softwareheritage.org/T75#12186"""
    fixed_rev = attr.evolve(
        rev,
        author=Person.from_fullname(rev.author.fullname.replace(b" <", b"  <")),
        committer=Person.from_fullname(rev.committer.fullname.replace(b" <", b"  <")),
    )
    if rev.id == fixed_rev.compute_hash():
        print(f"Fixable revision {rev.id.hex()} (added space in fullname separator)")
        return True

    fixed_rev = attr.evolve(
        rev,
        author=Person.from_fullname(rev.author.fullname.replace(b"> ", b">  ")),
        committer=Person.from_fullname(rev.committer.fullname.replace(b"> ", b">  ")),
    )
    if rev.id == fixed_rev.compute_hash():
        # eg. 40060fe3459cf103a143c324f99c2233a8e53825
        print(f"Fixable revision {rev.id.hex()} (added space after fullname>)")
        return True

    fixed_rev = attr.evolve(
        rev,
        author=Person.from_fullname(rev.author.fullname.replace(b" <", b"<")),
        committer=Person.from_fullname(rev.committer.fullname.replace(b" <", b"<")),
    )
    if rev.id == fixed_rev.compute_hash():
        # eg. 40060fe3459cf103a143c324f99c2233a8e53825
        print(f"Fixable revision {rev.id.hex()} (removed space before email)")
        return True

    return False


def fixable_revision_missing_headers(rev, d):
    """item 4 on https://forge.softwareheritage.org/T75#12186"""
    # TODO: try other orders?
    fixed_rev = attr.evolve(
        rev, extra_headers=(*rev.extra_headers, (b"encoding", b"latin-1")),
    )
    if rev.id == fixed_rev.compute_hash():
        print(f"Fixable revision {rev.id.hex()} (added 'encoding latin-1' header)")
        return True
    else:
        return False


def handle_revision_mismatch(rev, d):
    if fixable_revision_gpgsig_newline(rev, d):
        return

    if fixable_revision_mergetag_newline(rev, d):
        return

    if fixable_revision_gpgsig_indent(rev, d):
        return

    if fixable_revision_extra_author_space(rev, d):
        return

    if fixable_revision_missing_headers(rev, d):
        return

    if rev.type == model.RevisionType.SUBVERSION:
        print(f"Possibly unfixable SVN revision: {rev.id.hex()}")
        return

    if (
        rev.message is not None
        and (b"--HG--\nbranch" in rev.message or rev.message.startswith(b"[r"))
        and not any(k.startswith(b"HG:") for k in dict(rev.extra_headers))
    ):
        # eg. 1004162164bc129dc13393223633364deb2e5ed6
        # and 0005ece50565d7b14d6f1ecbcdaf4958106d14b9
        print(f"Possibly missing 'HG:extra' header: {rev.id.hex()}")
        return

    if (
        rev.message is not None
        and b"Signed-off-by:" in rev.message
        and b"gpgsig" not in dict(rev.extra_headers)
    ):
        # eg. e003db8870056d44b0f2e3643d6769f26987ad68
        print(f"Possibly missing 'gpgsig' header: {rev.id.hex()}")
        return

    real_id = rev.compute_hash()
    print(
        f"Checksum mismatch on revision: "
        f"{rev.id.hex()} in journal, but recomputed as {real_id.hex()}.\n"
    )
    if rev.id.hex() not in ("c0004375bc09db6d48da2e6573ec15397ad76ca3",):
        if b"gpgsig" not in dict(rev.extra_headers):
            # Probably missing gpgsig header, nothing more we can do...
            return
        #sys.stderr.flush()
        #print("Exiting")
        #sys.stdout.flush()
        #exit(1)


def fixable_directory_with_changed_permissions(dir_, d):
    possible_rewrites = [(0o40000, 0o40755), (0o40000, 0o40775), (0o100755, 0o100744)]

    for nb_rewrites in range(1, len(possible_rewrites) + 1):
        for rewrite in itertools.combinations(possible_rewrites, nb_rewrites):
            rewrite_dict = dict(rewrite)
            fixed_entries = tuple(
                attr.evolve(entry, perms=rewrite_dict.get(entry.perms, entry.perms))
                for entry in dir_.entries
            )
            fixed_dir = attr.evolve(dir_, entries=fixed_entries)
            if fixed_dir == dir_:
                # pointless to recompute the hash
                continue
            if fixed_dir.compute_hash() == dir_.id:
                print(
                    f"Fixable directory {dir_.id.hex()} (rewrote perms: {rewrite_dict})"
                )

    return False


def directory_identifier_without_sorting(directory):
    """Like swh.model.identifiers.directory_identifier, but does not sort entries."""
    components = []

    for entry in directory["entries"]:
        components.extend(
            [
                identifiers._perms_to_bytes(entry["perms"]),
                b"\x20",
                entry["name"],
                b"\x00",
                identifiers.identifier_to_bytes(entry["target"]),
            ]
        )
    git_object = identifiers.format_git_object_from_parts("tree", components)
    return hashlib.new("sha1", git_object).hexdigest()


def directory_identifier_with_padding(directory):
    """Like swh.model.identifiers.directory_identifier, but does not sort entries."""
    components = []

    for entry in sorted(directory["entries"], key=identifiers.directory_entry_sort_key):
        components.extend(
            [
                b"\x00",
                "{:0>6}".format(  # zero-pad the perms
                    identifiers._perms_to_bytes(entry["perms"]).decode()
                ).encode(),
                b"\x20",
                entry["name"],
                identifiers.identifier_to_bytes(entry["target"]),
            ]
        )
    git_object = identifiers.format_git_object_from_parts("tree", components)
    return hashlib.new("sha1", git_object).hexdigest()


def handle_directory_mismatch(dir_, d):
    id_without_sorting = hash_to_bytes(
        directory_identifier_without_sorting(dir_.to_dict())
    )
    if dir_.id == id_without_sorting:
        print(f"Weird directory checksum {dir_.id.hex()} (computed without sorting)")
        return

    id_with_padding = hash_to_bytes(directory_identifier_with_padding(dir_.to_dict()))
    if dir_.id == id_with_padding:
        print(f"Fixable directory checksum {dir_.id.hex()}: padded perms")
        return

    if fixable_directory_with_changed_permissions(dir_, d):
        return

    real_id = dir_.compute_hash()
    print(
        f"Checksum mismatch on directory: "
        f"{dir_.id.hex()} in journal, but recomputed as {real_id.hex()}.\n"
    )


def process_objects(all_objects):
    for (object_type, objects) in all_objects.items():
        cls = getattr(model, object_type.capitalize())
        for object_dict in objects:
            object_ = cls.from_dict(object_dict)
            real_id = object_.compute_hash()
            if object_.id != real_id:
                if object_type == "revision":
                    handle_revision_mismatch(object_, object_dict)
                elif object_type == "directory":
                    handle_directory_mismatch(object_, object_dict)
                else:
                    assert False, object_type


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
        # "debug": "all",
    }

    client = get_journal_client(
        "kafka",
        brokers=[f"broker{i}.journal.softwareheritage.org:9093" for i in range(1, 5)],
        group_id="swh-vlorentz-T75-check-checksum-02",
        #object_types=["directory", "snapshot"],
        object_types=["directory", "revision", "snapshot"],
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
