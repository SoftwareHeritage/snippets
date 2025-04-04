#!/usr/bin/env python3

# Copyright (C) 2023  The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information

import difflib
import sys

import click
import ndjson
from swh.model.hashutil import hash_to_hex
from swh.model.swhids import CoreSWHID, ObjectType
from swh.storage import get_storage
from swh.storage.algos.diff import diff_revision

type_to_obj_type = {
    "file": ObjectType.CONTENT,
    "dir": ObjectType.DIRECTORY,
    "rev": ObjectType.REVISION,
}


@click.command()
@click.option(
    "--storage-url",
    default="http://moma.internal.softwareheritage.org:5002/",
    show_default=True,
    help="SWH storage service URL",
)
@click.option(
    "--with-content-diffs",
    default=False,
    is_flag=True,
    show_default=True,
    help="Compute diffs of modified files and add them in output",
)
@click.option(
    "--verbose",
    default=False,
    is_flag=True,
    show_default=True,
    help="Add more details about modified paths in output",
)
@click.option(
    "--track-renaming",
    default=False,
    is_flag=True,
    show_default=True,
    help=(
        "Wether to track files renaming, warning the used algorithm is quite "
        "naive and might fail for some edge cases. Enabling that option also "
        "enables verbose output."
    ),
)
@click.argument("rev_swhids", nargs=-1, required=False)
@click.pass_context
def run(ctx, storage_url, with_content_diffs, track_renaming, verbose, rev_swhids):
    """From a given list of revision SWHIDS, provided as arguments or read from
    standard input line by line, output the list of files each of them modifies
    (equivalent to "git diff --stat", but without the detail of the number of
    lines added/removed to each modified path) in NDJSON format.

    By default, output a list of modifications with their type (modify/insert/delete)
    and their modified path.
    """

    storage = get_storage("remote", url=storage_url)

    if not rev_swhids:
        rev_swhids = sys.stdin

    writer = ndjson.writer(sys.stdout, ensure_ascii=False)

    for rev_swhid in rev_swhids:
        rev_swhid = rev_swhid.rstrip("\n")
        if not rev_swhid:
            break
        rev_swhid = CoreSWHID.from_string(rev_swhid)
        rev_changes = diff_revision(storage, rev_swhid.object_id, track_renaming)

        for rev_change in rev_changes:
            if verbose or track_renaming:
                for state in ("from", "to"):
                    if rev_change[state]:
                        rev_change[state]["dir_id"] = str(
                            CoreSWHID(
                                object_type=ObjectType.DIRECTORY,
                                object_id=rev_change[state]["dir_id"],
                            )
                        )
                        rev_change[state]["target"] = str(
                            CoreSWHID(
                                object_type=type_to_obj_type[rev_change[state]["type"]],
                                object_id=rev_change[state]["target"],
                            )
                        )
                        rev_change[state]["name"] = rev_change[state]["name"].decode(
                            "utf-8", "replace"
                        )
                        for checksum in ("sha1", "sha1_git", "sha256"):
                            rev_change[state][checksum] = hash_to_hex(
                                rev_change[state][checksum]
                            )
            if rev_change["from_path"]:
                rev_change["from_path"] = rev_change["from_path"].decode(
                    "utf-8", "replace"
                )
            if rev_change["to_path"]:
                rev_change["to_path"] = rev_change["to_path"].decode("utf-8", "replace")

            rev_change["diff"] = None

            if with_content_diffs and rev_change["type"] == "modify":
                from_sha1 = rev_change["from"]["sha1"]
                to_sha1 = rev_change["to"]["sha1"]
                from_bytes = storage.content_get_data(from_sha1)
                to_bytes = storage.content_get_data(to_sha1)
                from_lines = from_bytes.decode("utf-8", "replace")
                to_lines = to_bytes.decode("utf-8", "replace")
                diff_lines = difflib.unified_diff(
                    from_lines.splitlines(keepends=True),
                    to_lines.splitlines(keepends=True),
                    fromfile=rev_change["from_path"],
                    tofile=rev_change["to_path"],
                )
                diff_str = "".join(diff_lines)
                rev_change["diff"] = diff_str

        if verbose or track_renaming:
            writer.writerow(rev_changes)
        else:
            row = []
            for rev_change in rev_changes:
                row.append(
                    {
                        "type": rev_change["type"],
                        "path": rev_change["to_path"] or rev_change["from_path"],
                    }
                )
                if with_content_diffs:
                    row[-1]["diff"] = rev_change["diff"]
            writer.writerow(row)
        sys.stdout.flush()


if __name__ == "__main__":
    run()
