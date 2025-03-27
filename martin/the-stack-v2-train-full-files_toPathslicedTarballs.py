#!/usr/bin/env python

"""
Requires: PyArrow

This turns Parquet files from `the-stack-v2-train-full-files` into tarballs where files
are dispatched as if managed by an uncompressed pathslicer objstorage (0:2/0:5)

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
import os
import io
from time import perf_counter
from datetime import datetime
import tarfile
import traceback
from concurrent.futures import ProcessPoolExecutor

from pathlib import Path
import pyarrow.dataset as ds

base = Path("/bettik/PROJECTS/pr-swh-codecommons/COMMON/the-stack-v2-train-full-files/data")

target = Path("/bettik/PROJECTS/pr-swh-codecommons/COMMON/the-stack-v2-pathsliced/")

ID_HASH_ALGO = "sha1"
ID_HEXDIGEST_LENGTH = 40
class PathSlicer:
    """
    yes this is copypasted from swh.objstorage.backends.pathslicing.PathSlicer
    but this will be running in non-swh envs
    """

    def __init__(self, root: str, slicing: str):
        self.root = root
        # Make a list of tuples where each tuple contains the beginning
        # and the end of each slicing.
        try:
            self.bounds = [
                slice(*(int(x) if x else None for x in sbounds.split(":")))
                for sbounds in slicing.split("/")
                if sbounds
            ]
        except TypeError:
            raise ValueError(
                "Invalid slicing declaration; "
                "it should be a of the form '<int>:<int>[/<int>:<int>]..."
            )

    def check_config(self):
        """Check the slicing configuration is valid.

        Raises:
            ValueError: if the slicing configuration is invalid.
        """
        if len(self):
            max_char = max(
                max(bound.start or 0, bound.stop or 0) for bound in self.bounds
            )
            if ID_HEXDIGEST_LENGTH < max_char:
                raise ValueError(
                    "Algorithm %s has too short hash for slicing to char %d"
                    % (ID_HASH_ALGO, max_char)
                )

    def get_directory(self, hex_obj_id: str) -> str:
        """Compute the storage directory of an object.

        See also: PathSlicer::get_path

        Args:
            hex_obj_id: object id as hexlified string.

        Returns:
            Absolute path (including root) to the directory that contains
            the given object id.
        """
        return os.path.join(self.root, *self.get_slices(hex_obj_id))

    def get_path(self, hex_obj_id: str) -> str:
        """Compute the full path to an object into the current storage.

        See also: PathSlicer::get_directory

        Args:
            hex_obj_id(str): object id as hexlified string.

        Returns:
            Absolute path (including root) to the object corresponding
            to the given object id.
        """
        return os.path.join(self.get_directory(hex_obj_id), hex_obj_id)

    def get_slices(self, hex_obj_id: str) -> list[str]:
        """Compute the path elements for the given hash.

        Args:
            hex_obj_id(str): object id as hexlified string.

        Returns:
            Relative path to the actual object corresponding to the given id as
            a list.
        """

        assert len(hex_obj_id) == ID_HEXDIGEST_LENGTH
        return [hex_obj_id[bound] for bound in self.bounds]

    def __len__(self) -> int:
        """Number of slices of the slicer"""
        return len(self.bounds)


def process_file(input_i):
    suffix = f"{input_i:05d}-of-00512"
    tar_file_path = target / f"train-{suffix}.tar.xz"
    if tar_file_path.exists():
        print(datetime.now().isoformat(), f"skipping existing {tar_file_path}", flush=True)
        return (tar_file_path, 0, 0)

    slicer = PathSlicer("", "0:2/0:5")
    start = perf_counter()
    total_length = 0

    dataset = ds.dataset(
        base / f"train-{suffix}.parquet",
        format="parquet",
    ).to_table(
        columns=["files"],
    )
    with tarfile.open(tar_file_path, "w:xz") as tar:
        for i in range(len(dataset[0])):
            files = dataset[0][i]
            for j in range(len(files)):
                try:
                    parsed_sha1 = files[j]["blob_id"].as_py()
                    content = files[j]["content"].as_py().encode("utf-8")
                    buffered = io.BytesIO(content)

                    sliced_path = slicer.get_path(parsed_sha1)
                    tarinfo = tarfile.TarInfo(name=sliced_path)
                    tarinfo.size = len(content)
                    total_length += tarinfo.size

                    tar.addfile(tarinfo, buffered)

                except Exception as e:
                    print(f"in dataset[0][{i}][{j}]: {e}", flush=True)
                    traceback.print_exc()
                    continue

    duration = perf_counter() - start
    return (tar_file_path, total_length, duration)

if __name__ == "__main__":
    global_start = perf_counter()
    print(datetime.now().isoformat(), "started")
    with ProcessPoolExecutor(max_workers=10) as executor:
        results = executor.map(process_file, range(512))
        for i, result in enumerate(results):
            tar_file_path, total_length, duration = result
            print(
                datetime.now().isoformat(),
                f"{i}: wrote {total_length} bytes in {tar_file_path} in {duration:.2f} seconds",
                flush=True,
            )
    print(
        datetime.now().isoformat(),
        f"done in {perf_counter() - global_start:.2f} seconds"
    )
