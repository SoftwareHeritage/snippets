import asyncio
from datetime import datetime
from typing import Callable, Iterator
from urllib.parse import urljoin
from pathlib import Path
import zlib
import aiohttp
import pyzstd
import tarfile
import io
import time
import os
import pyarrow.dataset as ds
from concurrent.futures import ProcessPoolExecutor
import shutil
# import aiomonitor

BASEDIR = Path("/bettik/PROJECTS/pr-swh-codecommons/COMMON")
TMP_ROOT = Path("/scratch/cargo/kirchgem")
TARGET_ROOT = BASEDIR / "the-stack-v2-pathsliced"
INPUT = BASEDIR / "sha1_to_download"
CONCURRENT_REQUESTS = 60
CONCURRENT_PROCESSES = 8

ID_HASH_ALGO = "sha1"
ID_HEXDIGEST_LENGTH = 40

MTIME = int(time.time())

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



class AWSObjStorageDownloader():
    """
    HTTPReadOnlyObjStorage hardcoded to AWS and without the whole SWH dependencies
    """
    def __init__(self,
                 client: aiohttp.ClientSession,
                 concurrency:int,
                 ids_generator: Iterator[bytes],
                 on_content: Callable[[bytes, bytes], None] = None
                 ):
        self.root_path = "https://softwareheritage.s3.amazonaws.com/content/"
        if not self.root_path.endswith("/"):
            self.root_path += "/"

        self.client = client
        self.concurrency = concurrency
        self.task_id = 0
        self.tasks = {}
        self.can_push_task = asyncio.Event()
        self.on_content = on_content
        self.ids_generator = ids_generator
        self.total_bytes = 0
        self.nb_objects = 0

    async def start(self):
        for obj_id in self.ids_generator:
            self.task_id += 1
            if len(self.tasks) >= self.concurrency:
                await self.can_push_task.wait()
                self.can_push_task.clear()
            task_id = f"dl-{self.task_id}"
            new_task = asyncio.create_task(self._get(obj_id), name=task_id)
            new_task.add_done_callback(self.on_task_done)
            self.tasks[task_id] = new_task
        while len(self.tasks) > 0:
            await asyncio.sleep(0.01) # leave some time for tasks to .set() !
            await self.can_push_task.wait()

    def on_task_done(self, task):
        if task.exception():
            print(datetime.now().isoformat(), f"/!\ task {task.get_name()} failed", task.exception())
        self.tasks.pop(task.get_name())
        self.can_push_task.set()

    async def _get_retry(self, url:str, do_retry:bool=True) -> bytes:
        # print(datetime.now().isoformat(), f"downloading {url}")
        async with self.client.get(url, timeout=60) as resp:
            if resp.status != 200:
                if do_retry:
                    await asyncio.sleep(5)
                    return await self._get_retry(url, do_retry=False)
                else:
                    resp.raise_for_status()
            return await resp.content.read()

    async def _get(self, obj_id: bytes):
        """
        Try and retry the download, uncompress, call on_content
        """
        try:
            content = await self._get_retry(self._path(obj_id))
        except Exception as e:
            raise ValueError(f"error: {obj_id.hex()} {e}")

        self.total_bytes += len(content)
        self.nb_objects += 1
        try:
            uncompressed = zlib.decompress(content, wbits=31)
        except (zlib.error):
            raise ValueError(
                f"content with sha1 hash {obj_id.hex()} is not a proper "
                "compressed file"
            )

        self.on_content(obj_id, uncompressed)

    def _path(self, obj_id:bytes) -> str:
        return urljoin(self.root_path, obj_id.hex())



def gen_hashes(parquet_file_path):
    """
    iterates on sha1 as bytes out of a parquet file generated by `the-stack-v2_gen-download_list.py`
    """
    dataset = ds.dataset(parquet_file_path, format="parquet")
    scanner = ds.Scanner.from_dataset(dataset, columns=["sha1"])
    for batch in scanner.to_batches():
        for item in batch.to_pylist():
            yield item["sha1"]


async def process_file(input: Path):
    # loop = asyncio.get_running_loop()
    # with aiomonitor.start_monitor(loop, hook_task_factory=True):

    target = TARGET_ROOT / input.name.replace(".parquet", ".tar.zst")
    if target.exists():
        print(datetime.now().isoformat(), f"skipping existing {target}")
        return
    print(datetime.now().isoformat(), f"STARTING {input}")

    tmp_target = TMP_ROOT / input.name.replace(".parquet", ".tar.zst")
    started = time.perf_counter()

    with pyzstd.open(tmp_target, "wb") as file:
        with tarfile.open(fileobj=file, mode="w") as tf:

            slicer = PathSlicer("", "0:2/0:5")

            def add_file(obj_id: bytes, content: bytes):
                sliced_path = slicer.get_path(obj_id.hex())
                tarinfo = tarfile.TarInfo(name=sliced_path)
                tarinfo.size = len(content)
                tarinfo.mtime = MTIME
                buffered = io.BytesIO(content)
                tf.addfile(tarinfo, buffered)

            async with aiohttp.ClientSession() as client:
                downloader = AWSObjStorageDownloader(
                    client,
                    CONCURRENT_REQUESTS,
                    gen_hashes(input),
                    add_file
                    )
                await downloader.start()

    shutil.move(tmp_target, target)
    done = time.perf_counter()
    spent = int(done - started)
    rate = downloader.total_bytes / (done-started) / 1024 / 1024

    print(
        datetime.now().isoformat(),
        f"DONE {input} downloaded {downloader.nb_objects} objects "
        f"({downloader.total_bytes} bytes) in {spent}s ({rate:.2f} MB/s)",
    )


def main(input: str):
    asyncio.run(process_file(Path(input)), debug=True)



if __name__ == "__main__":
    print(datetime.now().isoformat(), "starting")
    files = [str(f) for f in INPUT.glob("**/*.parquet")]
    with ProcessPoolExecutor(max_workers=CONCURRENT_PROCESSES) as executor:
        results = executor.map(main, files)
        for _ in results:
            pass
    print(datetime.now().isoformat(), "done")

