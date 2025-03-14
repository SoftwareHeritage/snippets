#!/usr/bin/env python

"""
Requires: PyArrow

This computes a list of sha1 (`blob_id` in bigcode's datasets) that are in
[the-stack-v2-full](https://huggingface.co/datasets/bigcode/the-stack-v2)
and not in `the-stack-v2-train-full-files`.

See constants below
"""

from time import perf_counter
from datetime import datetime

from pathlib import Path
import pyarrow as pa
import pyarrow.dataset as ds

# path to parquet files from the-stack-v2-full, ie. list of metadata
# TODO full version !
base = Path("/bettik/PROJECTS/pr-swh-codecommons/COMMON/the-stack-v2/data/ABAP")

# path to parquet files resulting from `the-stack-v2-train-full-files_extractIDs.py`
minus_extractedIDs = Path(
    "/bettik/PROJECTS/pr-swh-codecommons/COMMON/the-stack-v2-train-IDs"
)

target_folder = Path(
    "/bettik/PROJECTS/pr-swh-codecommons/COMMON/sha1_to_download"
)

def read_sort_base():
    complete_list = ds.dataset(base, format="parquet").to_table(columns=["blob_id"])
    print(datetime.now().isoformat(), "loaded complete list")
    sorted = complete_list.sort_by('blob_id')
    print(datetime.now().isoformat(), "sorted complete list")
    return sorted

def read_sort_minus():
    minus_list = ds.dataset(minus_extractedIDs, format="parquet").to_table(
        columns=["sha1"]
    )
    print(datetime.now().isoformat(), "loaded minus list")
    sorted_minus = minus_list.sort_by("sha1")
    print(datetime.now().isoformat(), "sorted minus list")
    return sorted_minus

def parse(string_scalar):
    return bytes.fromhex(string_scalar.as_py())

def diff(sorted_base, sorted_minus):
    print(datetime.now().isoformat(), "computing diff")
    max_base = len(sorted_base)
    max_minus = len(sorted_minus)
    percent = max_minus // 100
    i_base = 0
    parsed_base = parse(sorted_base[0][i_base])
    i_minus = 0
    diff = []
    while i_base < max_base and i_minus < max_minus:
        if parsed_base < sorted_minus[0][i_minus].as_py():
            diff.append(parsed_base)
            i_base += 1
            parsed_base = parse(sorted_base[0][i_base])
        elif parsed_base > sorted_minus[0][i_minus].as_py():
            # should not happen... but we don't care because `minus` is the dataset
            # with content included so we will have this content the other way
            i_minus += 1
        else:
            i_base += 1
            parsed_base = parse(sorted_base[0][i_base])
            i_minus += 1
        if i_minus % percent == 0:
            print(datetime.now().isoformat(), f"processed {(i_minus*100/max_minus)}% rows")
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
