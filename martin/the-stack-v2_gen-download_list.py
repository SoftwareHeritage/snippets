#!/usr/bin/env python

"""
Requires: PyArrow

This computes a list of sha1 (`blob_id` in bigcode's datasets) that are in
[the-stack-v2-full](https://huggingface.co/datasets/bigcode/the-stack-v2)
and not in `the-stack-v2-train-full-files`, in order to create a "to-download" list.

See constants below

One instance of `diff()` likely takes 20GB of RAM and 30 minutes.
"""

from concurrent.futures import ProcessPoolExecutor
from time import perf_counter
from datetime import datetime
import shutil

from pathlib import Path
import pyarrow as pa
import pyarrow.dataset as ds

# adapt this to the memory (seems to consume 16-20GB/worker)
MAX_WORKERS = 10

BASEDIR = "/bettik/PROJECTS/pr-swh-codecommons/COMMON"

# path to parquet files from the-stack-v2-full, ie. list of metadata
base = Path(f"{BASEDIR}/the-stack-v2/data")

# path to parquet files resulting from `the-stack-v2-train-full-files_extractSortedIDs.py`
minus_extractedIDs = Path(f"{BASEDIR}/the-stack-v2-train-sorted-IDs/part-0.parquet")

# local copy because we're not supposed to transfer 21GB 900 times
local_copy_extractedIDs = Path("/var/tmp/kirchgem/the-stack-v2-train-sorted-IDs.parquet")

target_folder = Path(f"{BASEDIR}/sha1_to_download")

def parse(string_scalar):
    return bytes.fromhex(string_scalar.as_py())

def read_sort_base(filename) -> list[bytes]:
    complete_list = ds.dataset(filename, format="parquet").to_table(columns=["blob_id"])
    # print(datetime.now().isoformat(), "loaded complete list")
    base_hashes = []
    for i in range(len(complete_list)):
        try:
            base_hashes.append(parse(complete_list[0][i]))
        except Exception as e:
            print(f"in complete_list[{i}]: {e}")
            continue
    base_hashes.sort()
    print(
        datetime.now().isoformat(),
        f"loaded and sorted {len(base_hashes)} hashes from {filename}",
    )
    return base_hashes

def read_sort_minus():
    minus_list = ds.dataset(local_copy_extractedIDs, format="parquet").to_table(
        columns=["sha1"]
    )
    print(datetime.now().isoformat(), "loaded sorted  minus list")
    return minus_list

def diff(sorted_base, sorted_minus):
    print(datetime.now().isoformat(), "computing diff")
    max_base = len(sorted_base)
    max_minus = len(sorted_minus)
    # percent = max_minus // 100
    i_base = 0
    i_minus = 0
    parsed_minus = sorted_minus[0][i_minus].as_py()
    diff = []
    while i_base < max_base and i_minus < max_minus:
        if sorted_base[i_base] < parsed_minus:
            diff.append(sorted_base[i_base])
            i_base += 1
        elif sorted_base[i_base] > parsed_minus:
            # should not happen... but we don't care because `minus` is the dataset
            # with content included so we won't miss that content anyway.
            i_minus += 1
            parsed_minus = sorted_minus[0][i_minus].as_py()
        else:
            i_base += 1
            i_minus += 1
            parsed_minus = sorted_minus[0][i_minus].as_py()
        # if i_minus % percent == 1:
        #     print(datetime.now().isoformat(), f"processed {(i_minus*100/max_minus):.2f}% rows")
    return diff

def process_file(filename):
    basename = str(Path(filename).relative_to(base)).replace('/', '_').removesuffix(".parquet")
    basename_template = basename + "-{i}.parquet"
    existing_file = basename_template.format(i=0)
    if (target_folder / existing_file).exists():
        return (None, existing_file)

    sorted_minus = read_sort_minus()
    sorted_base = read_sort_base(filename)
    result = diff(sorted_base, sorted_minus)

    schema = pa.schema(
        {
            "sha1": pa.binary(20),
        }
    )
    target = pa.Table.from_pydict(
        {
            "sha1": result,
        },
        schema=schema,
    )

    ds.write_dataset(
        target,
        target_folder,
        format="parquet",
        basename_template=basename_template,
        existing_data_behavior="overwrite_or_ignore",
    )

    return (len(result), existing_file)


if __name__ == "__main__":
    global_start = perf_counter()
    print(datetime.now().isoformat(), "starting")

    local_copy_extractedIDs.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(minus_extractedIDs, local_copy_extractedIDs)
    print(datetime.now().isoformat(), f"copied locally: {local_copy_extractedIDs}")

    files = [str(f) for f in base.glob("**/*.parquet")]
    with ProcessPoolExecutor(max_workers=MAX_WORKERS) as executor:
        results = executor.map(process_file, files)
        for i, result in enumerate(results):
            nb_hashes, filename = result
            if nb_hashes is None:
                print(datetime.now().isoformat(), f"skipping {filename}")
            else:
                print(
                    datetime.now().isoformat(),
                    f"Wrote {nb_hashes} hashes to {filename}",
                )

    print(datetime.now().isoformat(), "cleaning")
    shutil.rmtree(local_copy_extractedIDs.parent)

    print(
        datetime.now().isoformat(),
        f"done in {perf_counter() - global_start:.2f} seconds"
    )
