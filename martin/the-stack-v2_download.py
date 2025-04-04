# This harass S3 to download objects listed in a parquet file having at least a
# "sha1":pa.binary(20) column (like, built with the-stack-v2_gen-download_list.py)
#
# Requires:
# - aiohttp
# - certifi
# - pyzstd
# - pyarrow

import asyncio
from datetime import datetime
from typing import Callable, Iterator
from urllib.parse import urljoin
from pathlib import Path
import zlib
import aiohttp
import certifi
import ssl
import pyzstd
import tarfile
import io
import time
import os
import pyarrow.dataset as ds
from concurrent.futures import ProcessPoolExecutor
import shutil
import random
# import aiomonitor

##### adapt these constants to your local coaster 🎢
# you might also have to adapt calls to shutil.move
BASEDIR = Path("/bettik/PROJECTS/pr-swh-codecommons/COMMON")
TARGET_ROOT = BASEDIR / "the-stack-v2-pathsliced"
INPUT = BASEDIR / "sha1_to_download"
TMP_ROOT = Path("/silenus/PROJECTS/pr-swh-codecommons/COMMON")
CONCURRENT_REQUESTS = 60
CONCURRENT_PROCESSES = 15

# how many bytes of *input* (yes, Parquet files) are processed per second of execution ?
# you'll need a few attempts to estimate this, then processes can estimate if they'll be
# able to process a batch before $OAR_JOB_WALLTIME_SECONDS - or, don't provide an
# env with $OAR_JOB_WALLTIME_SECONDS
INPUT_RATE=7000
##### 🚀

ID_HASH_ALGO = "sha1"
ID_HEXDIGEST_LENGTH = 40

MTIME = int(time.time())

class PathSlicer:
    """
    yes this is copypasted from swh.objstorage.backends.pathslicing.PathSlicer
    because this will be running in non-swh envs
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
    HTTPReadOnlyObjStorage hardcoded to AWS, without the whole SWH dependencies, with
    fancy counters and the ability to run concurrent queries
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
        self.total_bytes_uncompressed = 0
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
        await asyncio.gather(*self.tasks.values())

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
        try:
            uncompressed = zlib.decompress(content, wbits=31)
        except (zlib.error):
            raise ValueError(
                f"content with sha1 hash {obj_id.hex()} is not a proper "
                "compressed file"
            )

        self.total_bytes += len(content)
        self.total_bytes_uncompressed += len(uncompressed)
        self.nb_objects += 1
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


async def process_file(input: Path, max_timestamp: int):
    """
    This decides independantly to process input or not, if
     * it would take too much time (ie. might end after max_timestamp, at INPUT_RATE)
     * it is already processed, or being processed (in which case the empty target file is just a flag)
    """

    loop = asyncio.get_running_loop()
    loop.slow_callback_duration = 10.

    # with aiomonitor.start_monitor(loop, hook_task_factory=True):

    target = TARGET_ROOT / input.name.replace(".parquet", ".tar.zst")
    if target.exists():
        # print(datetime.now().isoformat(), f"skipping existing {target}")
        return

    estimated_end = time.time() + input.stat().st_size / INPUT_RATE
    if estimated_end >= max_timestamp:
        # eta = datetime.fromtimestamp(estimated_end).isoformat()
        # print(
        #     datetime.now().isoformat(),
        #     f"skipping {target} because it might finish too late (ETA: {eta})",
        # )
        return

    print(datetime.now().isoformat(), f"STARTING {input}")
    target.touch(exist_ok=False)
    tmp_target = TMP_ROOT / (target.name + ".writing")
    started = time.perf_counter()

    # SSL conf does not seem greatly bound to Python on cargo.ciment
    # enable_cleanup_closed may avoid memory leaks in Python<3.12 (but we still have a leak somewhere - arrow maybe ?)
    ssl_context = ssl.create_default_context(cafile=certifi.where())
    connector = aiohttp.TCPConnector(ssl=ssl_context, enable_cleanup_closed=True)

    # 2MB writing buffer should be nicer to network storages we're targeting
    with pyzstd.ZstdFile(tmp_target, "wb", write_size=2*1024*1024) as file:
        with tarfile.open(fileobj=file, mode="w") as tf:

            slicer = PathSlicer("", "0:2/0:5")

            def add_file(obj_id: bytes, content: bytes):
                sliced_path = slicer.get_path(obj_id.hex())
                tarinfo = tarfile.TarInfo(name=sliced_path)
                tarinfo.size = len(content)
                tarinfo.mtime = MTIME
                buffered = io.BytesIO(content)
                tf.addfile(tarinfo, buffered)

            async with aiohttp.ClientSession(connector=connector) as client:
                downloader = AWSObjStorageDownloader(
                    client,
                    CONCURRENT_REQUESTS,
                    gen_hashes(input),
                    add_file
                    )
                await downloader.start()

    # transfer "file.writing" to bettik
    transferred_tmp = TARGET_ROOT / tmp_target.name
    shutil.move(tmp_target, transferred_tmp)
    # rename on bettik to the final file name, marking that batch as completed
    shutil.move(transferred_tmp, target)

    # flex those rates to the log
    done = time.perf_counter()
    spent = int(done - started)
    rate = downloader.total_bytes / (done-started) / 1024 / 1024
    objrate = downloader.nb_objects / (done - started)
    print(
        datetime.now().isoformat(),
        f"DONE {input} downloaded {downloader.nb_objects} objects "
        f"({downloader.total_bytes} bytes compressed, "
        f"{downloader.total_bytes_uncompressed} uncompressed) in {spent}s "
        f"({objrate} objects/s, {rate:.2f} MB/s transferred)",
    )


def main(param):
    input, max_timestamp = param
    asyncio.run(process_file(Path(input), max_timestamp), debug=True)



if __name__ == "__main__":
    print(datetime.now().isoformat(), "starting")

    try:
        job_max_timestamp = int(os.environ["OAR_JOB_WALLTIME_SECONDS"]) + time.time() - 10
    except KeyError:
        job_max_timestamp = 9999999999
        print("can't find environment variable OAR_JOB_WALLTIME_SECONDS, so batches "
              "will not predict their runtime with INPUT_RATE. Hope you don't have a "
              "time limit !")

    files = [str(f) for f in INPUT.glob("**/*.parquet")]
    # we shuffle the files list so multiple machines running in parallel would very unlikely
    # check that a flag file exist at the same time.
    random.shuffle(files)
    params = zip(files, [job_max_timestamp]*len(files))

    with ProcessPoolExecutor(max_workers=CONCURRENT_PROCESSES) as executor:
        results = executor.map(main, params)
        for _ in results:
            pass
    print(datetime.now().isoformat(), "done")
