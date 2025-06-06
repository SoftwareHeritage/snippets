#!/usr/bin/env python

"""
Requires: PyArrow

This computes a list of sha1 (`blob_id` in bigcode's datasets) that are in
[the-stack-v2-full](https://huggingface.co/datasets/bigcode/the-stack-v2)
and not in `the-stack-v2-train-full-files`, in order to create a "to-download" list.

See constants below

One instance of `diff()` likely takes 2GB of RAM and 30 minutes.

note: to quickly check how many rows are in the dataset, use
    import pyarrow.dataset as ds
    d = ds.dataset(path)
    sum(f.count_rows() for f in d.get_fragments())
"""

from concurrent.futures import ProcessPoolExecutor
from time import perf_counter
from datetime import datetime
import shutil

from pathlib import Path
import pyarrow as pa
import pyarrow.dataset as ds

# adapt this to the CPU/memory (seems to consume less than 2GB/worker)
MAX_WORKERS = 30

BASEDIR = "/bettik/PROJECTS/pr-swh-codecommons/COMMON"

# path to parquet files from the-stack-v2-full, ie. list of metadata
base = Path(f"{BASEDIR}/the-stack-v2/data")

# path to parquet files resulting from `the-stack-v2-train-full-files_extractSortedIDs.py`
minus_extractedIDs = Path(f"{BASEDIR}/the-stack-v2-train-sorted-IDs")

# local copy because we're not supposed to transfer 21GB 900 times
local_copy_extractedIDs = Path("/var/tmp/kirchgem/the-stack-v2-train-sorted-IDs")

target_folder = Path(f"{BASEDIR}/sha1_to_download")


def read_sort_base(filename) -> list[bytes]:
    base_hashes = []
    dataset = ds.dataset(filename, format="parquet")
    scanner = ds.Scanner.from_dataset(dataset, columns=["blob_id"])
    for batch in scanner.to_batches():
        for item in batch.to_pylist():
            base_hashes.append(bytes.fromhex(item['blob_id']))
    base_hashes.sort()
    print(
        datetime.now().isoformat(),
        f"loaded and sorted {len(base_hashes)} hashes from {filename}",
    )
    return base_hashes

def read_sort_minus():
    """
    We use a hacky method (use_threads=False) when reading/writing this file, to ensure
    we find back hashes sorted as when they were written.
    But we check the order just to be sure...
    """
    part_i = 0
    previous = None
    while True:
        part_path = local_copy_extractedIDs / f"part-{part_i}.parquet"
        if not part_path.exists():
            break
        dataset = ds.dataset(part_path, format="parquet")
        scanner = ds.Scanner.from_dataset(dataset, columns=["sha1"], use_threads=False)
        for batch in scanner.to_batches():
            for item in batch.to_pylist():
                c = item['sha1']
                if previous is not None and previous > c:
                    raise Exception(f"previous={previous} c={c} unordered")
                previous = c
                yield c
        part_i += 1
    yield None



def diff(sorted_base, sorted_minus):
    print(datetime.now().isoformat(), "computing diff")
    max_base = len(sorted_base)
    i_base = 0
    parsed_minus = next(sorted_minus)
    diff = []
    while i_base < max_base:
        if parsed_minus is None or sorted_base[i_base] < parsed_minus:
            diff.append(sorted_base[i_base])
            i_base += 1
        elif sorted_base[i_base] > parsed_minus:
            if parsed_minus is not None:
                parsed_minus = next(sorted_minus)
        else:
            i_base += 1
            if parsed_minus is not None:
                parsed_minus = next(sorted_minus)
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
    shutil.copytree(minus_extractedIDs, local_copy_extractedIDs)
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
    shutil.rmtree(local_copy_extractedIDs)

    print(
        datetime.now().isoformat(),
        f"done in {perf_counter() - global_start:.2f} seconds"
    )
