#!/usr/bin/env python

"""
Requires: PyArrow

This computes a list of sha1 (`blob_id` in bigcode's datasets) that are in
[the-stack-v2-full](https://huggingface.co/datasets/bigcode/the-stack-v2)
and not in `the-stack-v2-train-full-files`, in order to create a "to-download" list.

See constants below
"""

from time import perf_counter
from datetime import datetime

from pathlib import Path
import pyarrow as pa
import pyarrow.dataset as ds

# path to parquet files from the-stack-v2-full, ie. list of metadata
# TODO full version !
base = Path(
    "/bettik/PROJECTS/pr-swh-codecommons/COMMON/the-stack-v2/data/JSON/train-00063-of-00064.parquet"
)

# path to parquet files resulting from `the-stack-v2-train-full-files_extractSortedIDs.py`
minus_extractedIDs = Path(
    "/bettik/PROJECTS/pr-swh-codecommons/COMMON/the-stack-v2-train-sorted-IDs"
)

target_folder = Path(
    "/bettik/PROJECTS/pr-swh-codecommons/COMMON/sha1_to_download"
)

def parse(string_scalar):
    return bytes.fromhex(string_scalar.as_py())

def read_sort_base() -> list[bytes]:
    complete_list = ds.dataset(base, format="parquet").to_table(columns=["blob_id"])
    print(datetime.now().isoformat(), "loaded complete list")
    base_hashes = []
    for i in range(len(complete_list)):
        try:
            base_hashes.append(parse(complete_list[i]["blob_id"]))
        except Exception as e:
            print(f"in complete_list[{i}]: {e}")
            continue
    print(datetime.now().isoformat(), " - parsed")
    base_hashes.sort()
    print(datetime.now().isoformat(), " - sorted")
    return base_hashes

def read_sort_minus():
    minus_list = ds.dataset(minus_extractedIDs, format="parquet").to_table(
        columns=["sha1"]
    )
    print(datetime.now().isoformat(), "loaded sorted  minus list")
    return minus_list

def diff(sorted_base, sorted_minus):
    print(datetime.now().isoformat(), "computing diff")
    max_base = len(sorted_base)
    max_minus = len(sorted_minus)
    percent = max_minus // 100
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
        if i_minus % percent == 1:
            print(datetime.now().isoformat(), f"processed {(i_minus*100/max_minus):.2f}% rows")
    return diff

if __name__ == "__main__":
    global_start = perf_counter()
    print(datetime.now().isoformat(), "starting")

    sorted_minus = read_sort_minus()
    sorted_base = read_sort_base()
    result = diff(sorted_base, sorted_minus)

    print(datetime.now().isoformat(), f"diff computed, contains {len(result)} hashes")

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
        basename_template="download_list-{i}",
        #existing_data_behavior='overwrite_or_ignore',
    )

    print(
        datetime.now().isoformat(),
        f"done in {perf_counter() - global_start:.2f} seconds"
    )
