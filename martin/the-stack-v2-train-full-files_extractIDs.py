#!/usr/bin/env python

"""
Requires: PyArrow

This turns Parquet files from `the-stack-v2-train-full-files` into smaller Parquet
files containing only 3 columns `(sha1, sha1_git, length_bytes)` using one row per file
from the original dataset.
Tune constants below before running.

Relevant column/fields in the table:

  - name: files
    list:
    - name: blob_id (=sha1)
      dtype: string
    - name: path
      dtype: string
    - name: content_id (=sha1_git)
      dtype: string
    - name: language
      dtype: string
    - name: content
      dtype: string
    - name: length_bytes
      dtype: int64

"""
from concurrent.futures import ProcessPoolExecutor
from time import perf_counter
from datetime import datetime

from pathlib import Path
import pyarrow as pa
import pyarrow.dataset as ds

# adapt this to the available bandwith and memory (rule of thumb is 5GB/worker)
MAX_WORKERS=15

base=Path("/bettik/PROJECTS/pr-swh-codecommons/COMMON/the-stack-v2-train-full-files/data")

target_folder = Path(
    "/bettik/PROJECTS/pr-swh-codecommons/COMMON/the-stack-v2-train-IDs"
)

def process_file(input_i):
    start = perf_counter()
    suffix = f"{input_i:05d}-of-00512"

    dataset = ds.dataset(
        base / f"train-{suffix}.parquet",
        format="parquet",
    ).to_table(
        columns=["files"],
    )
    sha1 = []
    sha1_git = []
    length = []
    for i in range(len(dataset[0])):
        files = dataset[0][i]
        for j in range(len(files)):
            try:
                parsed_sha1 = bytes.fromhex(files[j]["blob_id"].as_py())
                parsed_sha1_git = bytes.fromhex(files[j]["content_id"].as_py())
                parsed_length = files[j]["length_bytes"].as_py()
            except Exception as e:
                print(f"in dataset[0][{i}][{j}]: {e}")
                continue
            sha1.append(parsed_sha1)
            sha1_git.append(parsed_sha1_git)
            length.append(parsed_length)
        # if i % 10000 == 0:
        #     print(f"processed {i} input rows, resulting in {len(sha1)} rows")

    schema = pa.schema(
        {
            "sha1": pa.binary(20),
            "sha1_git": pa.binary(20),
            "length_bytes": pa.int64(),
        }
    )
    target = pa.Table.from_pydict(
        {
            "sha1": sha1,
            "sha1_git": sha1_git,
            "length_bytes": length,
        },
        schema=schema,
    )

    ds.write_dataset(
        target,
        target_folder,
        format="parquet",
        basename_template="ids-"+suffix+"-{i}",
        existing_data_behavior='overwrite_or_ignore',
    )
    duration = perf_counter() - start
    return duration

if __name__ == "__main__":
    global_start = perf_counter()
    print(datetime.now().isoformat(), "started")
    with ProcessPoolExecutor(max_workers=MAX_WORKERS) as executor:
        results = executor.map(process_file, range(512))
        for i, result in enumerate(results):
            print(
                datetime.now().isoformat(),
                f"processed {i} in {result:.2f} seconds",
            )
    print(
        datetime.now().isoformat(),
        f"done in {perf_counter() - global_start:.2f} seconds"
    )
