#!/usr/bin/env python

"""
Requires: PyArrow

This turns Parquet files from `the-stack-v2-train-full-files` into smaller Parquet
file containing only 1 *sorted* column `sha1_git` using one row per file
from the original dataset.
Tune constants below before running.

Initial version used pa.Table.sort_by but it seems faster to convert to bytes, then sort
as list[bytes].
"""
from time import perf_counter
from datetime import datetime

from pathlib import Path
import pyarrow as pa
import pyarrow.dataset as ds

base=Path("/bettik/PROJECTS/pr-swh-codecommons/COMMON/the-stack-v2-train-full-files/data")

target_folder = Path(
    "/bettik/PROJECTS/pr-swh-codecommons/COMMON/the-stack-v2-train-sorted-IDs"
)

def read_file(input_i:int, sha1s:list[bytes]) -> None:
    suffix = f"{input_i:05d}-of-00512"

    dataset = ds.dataset(
        base / f"train-{suffix}.parquet",
        format="parquet",
    ).to_table(
        columns=["files"],
    )
    for i in range(len(dataset[0])):
        files = dataset[0][i]
        for j in range(len(files)):
            try:
                parsed_sha1 = bytes.fromhex(files[j]["blob_id"].as_py())
            except Exception as e:
                print(f"in dataset[0][{i}][{j}]: {e}")
                continue
            sha1s.append(parsed_sha1)

    return sha1s

if __name__ == "__main__":
    global_start = perf_counter()
    print(datetime.now().isoformat(), "started")
    sha1s = []
    for i in range(512):
        start = perf_counter()
        read_file(i, sha1s)
        duration = perf_counter() - start
        print(
            datetime.now().isoformat(),
            f"processed {i} in {duration:.2f} seconds",
        )
    print(datetime.now().isoformat(), "sorting")
    sha1s.sort()
    print(datetime.now().isoformat(), "writing...")

    schema = pa.schema(
        {
            "sha1": pa.binary(20),
        }
    )
    target = pa.Table.from_pydict(
        {
            "sha1": sha1s,
        },
        schema=schema,
    )

    ds.write_dataset(
        target,
        target_folder,
        format="parquet",
    )

    print(
        datetime.now().isoformat(),
        f"done in {perf_counter() - global_start:.2f} seconds"
    )
