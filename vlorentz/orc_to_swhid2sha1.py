"""
Given the path to a directory containing .orc files for contents (eg. downloaded with
``aws s3 cp -r s3://softwareheritage/graph/2022-04-25/orc/content/ ./content/``)
and a destination path, writes ``.csv.zst`` files at the destination, with
``SWHID,sha1`` as header, usable as a map between both hashes.
"""

import functools
import math
import multiprocessing
from pathlib import Path
import os
import random
import sys

import pyarrow.fs
import pyarrow.orc
import pyzstd

PROCESSES = None  # defaults to about the number of CPUs

try:
    (_, input_dir, output_dir) = sys.argv
except ValueError:
    print(
        f"Syntax: {sys.argv[0]} path/to/orc/content/ path/to/output/dir/",
        file=sys.stderr,
    )
    sys.exit(1)


input_dir = Path(input_dir)
output_dir = Path(output_dir)

output_dir.mkdir(exist_ok=True)
if not input_dir.exists():
    raise ValueError(f"{input_dir} does not exist")


def export_file(shard_name, progress_dict):
    progress_dict[shard_name] = 0.0
    input_path = os.path.join(input_dir, shard_name)
    output_path = os.path.join(output_dir, shard_name.replace(".orc", ".csv.zst"))
    tmp_output_path = output_path + ".tmp"

    # Open output, write header
    with pyzstd.open(tmp_output_path, "wt") as output_fd:
        output_fd.write(f"SWHID,sha1\r\n")

        # Open input shard, read stripe by stripe
        of = pyarrow.orc.ORCFile(input_path)
        for stripe_id in range(of.nstripes):
            # Declare and check schema
            columns = ["sha1", "sha1_git"]
            stripe = of.read_stripe(stripe_id, columns=columns)
            type_ = stripe.schema.field("sha1").type
            assert type_ == "string", type_
            type_ = stripe.schema.field("sha1_git").type
            assert type_ == "string", type_

            # For each row in the stripe, write a CSV row
            for sha1, sha1_git in zip(stripe.column("sha1"), stripe.column("sha1_git")):
                output_fd.write(f"swh:1:cnt:{sha1_git},{sha1}\r\n")

            # Update and print progress
            progress_dict[shard_name] += 1 / of.nstripes
            progress = sum(progress_dict.values())
            progress_permille = int(progress * 1000 / len(shards))
            if random.randint(0, 10 * PROCESSES) == 0:
                # print progress approx once every 10 stripes
                print(f"{progress_permille/10}% stripes done")

    # Atomically write the output file
    os.replace(tmp_output_path, output_path)

    progress_dict[shard_name] = 1.0


shards = list(os.listdir(input_dir))

if PROCESSES is None:
    PROCESSES = multiprocessing.cpu_count()

    # Upper-round the number of processes to a multiple of the number of shards,
    # to evenly distribute the load
    shards_per_process = len(shards) / PROCESSES
    PROCESSES = int(len(shards) / math.floor(shards_per_process))

print(
    f"Converting {len(shards)} shards from {input_dir} to "
    f"{output_dir} using {PROCESSES} processes"
)

with multiprocessing.Manager() as manager:
    progress_dict = manager.dict()  # maps shard name to ratio completed
    worker = functools.partial(export_file, progress_dict=progress_dict)

    with multiprocessing.Pool(PROCESSES) as pool:
        for _ in pool.imap_unordered(worker, shards):
            pass
        print("Done.")
