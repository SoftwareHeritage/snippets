#!/usr/bin/env -S python -u

# OAR -d /home/kirchgem/2025-06-17-bench1
# OAR -l /nodes=2,walltime=02:00:00
# OAR --name swh-fuse-hyply1
# OAR --project pr-swh-codecommons
# OAR --stdout stdout.log
# OAR --stderr stderr.log


from time import perf_counter, sleep
from pathlib import Path
from subprocess import run, Popen, PIPE
from tempfile import TemporaryDirectory
from concurrent.futures import ProcessPoolExecutor
import logging
from sys import argv, stdout
from os import environ
from threading import Thread
from queue import Queue, Empty
import socket

log = logging.getLogger()
log.setLevel(logging.DEBUG)

HOSTNAME = socket.gethostname()

PROCESS_PER_NODE = 200
NB_DIR_PER_NODE=200

# this concatenates 630MB worth of dir IDS, ie. 660000000 bytes, ie. 33 million IDs
LISTING="/hoyt/pr-swh-codecommons/the-stack-v2-directoryIDs"

def params_generator():
    """
    For each worker node, generate the offset in LISTING that it should start from
    """
    # TODO
    yield 0
    yield 1000000


class SwhFuseContext:
    """
    Mounts the SWH archive as a context manager, in a namespace, over a temporary folder.
    We advise you configure `swh-fuse` with care, possibly via the `SWH_CONFIG_FILE`
    environment variable
    """

    def __init__(self, target_dir):
        self.mountpoint = TemporaryDirectory()
        environ["SWH_CONFIG_FILE"] = "config.yml" # file created by graphjob.sh
        self.swhfuse = Popen(
            [
                "unshare",
                "--pid",
                "--kill-child",
                "--user",
                "--map-root-user",
                "--mount",
                "swh",
                "fs",
                "mount",
                "-f",
                self.mountpoint.name,
            ],
            stderr=PIPE,
            stdin=PIPE,
            stdout=PIPE,
        )
        self.target = target_dir

    def __enter__(self):
        archive_root = Path(f"/proc/{self.swhfuse.pid}/root{self.mountpoint.name}/archive")
        attempts = 0
        while not archive_root.is_dir():
            attempts += 1
            if attempts >= 60:
                raise RuntimeError("We've been waiting for more than a minute for the mount to happen. Aborting.")
            sleep(1)
        return Path(f"/proc/{self.swhfuse.pid}/root{self.mountpoint.name}/{self.target}")

    def __exit__(self, type, value, traceback):
        if not self.swhfuse.poll():
            self.swhfuse.terminate()
        self.mountpoint.cleanup()

def python_sloc(directory: str) -> int:
    pysloc = 0

    with SwhFuseContext(directory) as swhroot:
        for f in swhroot.glob("**/*.py"):
            try:
                with open(f) as fp:
                    pysloc += sum(1 for line in fp)
            except Exception:
                pass

    return pysloc


def python_files(directory: str) -> int:
    nbfiles = 0
    with SwhFuseContext(directory) as swhroot:
        # print(f"globbing {swhroot}...")
        for f in swhroot.glob("**/*.py"):
            nbfiles += 1
    return nbfiles


def scancode(directory: str) -> int:
    with SwhFuseContext(directory) as swhroot:
        run(
            [
                "scancode",
                "--license",
                # doc suggests to add --copyright --package --email --info
                "-n",
                "6",
                "--json-pp",
                "/dev/null",
                swhroot.absolute(),
            ]
        )
    return 0

def hyply(directory: str) -> int:
    with SwhFuseContext(directory) as swhroot:
        _ = run(["hyply", swhroot.absolute()], capture_output=True, text=True)
    return 0


def gen_paths(listfile, nb_jobs, offset):
    generated = 0
    with open(listfile, 'rb') as f:
        f.seek(20*offset)
        while generated < nb_jobs:
            p = f"archive/swh:1:dir:{f.read(20).hex()}"
            yield p
            generated += 1

CASE=hyply

def worker_function(param):
    log.info("starting worker node(%s)", param)
    start = perf_counter()
    counted = 0

    storage_server = Popen("swh storage -C config_storage.yml rpc-serve".split(),
            stderr=PIPE,
            stdin=PIPE,
            stdout=PIPE,
        )

    try:
        with ProcessPoolExecutor(max_workers=PROCESS_PER_NODE) as executor:
            results = executor.map(CASE, gen_paths(LISTING, NB_DIR_PER_NODE, int(param)))
            for _ in results:
                counted += 1
    finally:
        if not storage_server.poll():
            storage_server.terminate()

    log.info(
        "%d dirs scanned in %f seconds over %d workers",
        counted,
        perf_counter() - start,
        PROCESS_PER_NODE,
    )
    log.info("stopping  worker node(%s)", param)


########## wrappers


def setup_logging(hostname):
    ch = logging.StreamHandler(stdout)
    ch.setLevel(logging.DEBUG)
    formatter = logging.Formatter(
        "%(asctime)s - " + hostname + " - %(levelname)s - %(message)s"
    )
    ch.setFormatter(formatter)
    log.addHandler(ch)


def node_driver(q, node_name):
    while True:
        try:
            p = q.get_nowait()
            params = ["oarsh", node_name, __file__, p]
            run(params, stdout=stdout, stderr=stdout)
        except Empty:
            log.info("No more jobs for %s", node_name)
            return


def main_head():
    node_file = environ.get("OAR_NODE_FILE")
    with open(node_file) as f:
        nodes = set(f.readlines())
    q = Queue()
    for i in params_generator():
        q.put(i)
    log.info("Loaded nodes list and parameters queue")
    driver_threads = []
    for node in nodes:
        driver_thread = Thread(target=node_driver, args=(q, node.strip()))
        driver_threads.append(driver_thread)
        driver_thread.start()
    for t in driver_threads:
        t.join()


if __name__ == "__main__":
    global_start = perf_counter()
    if len(argv) == 1:
        HOSTNAME += "(head)"
    setup_logging(HOSTNAME)

    if len(argv) > 1:
        worker_function(argv[1])
    else:
        log.info("Hello")
        main_head()
        log.info("Finished in %fs", perf_counter() - global_start)
