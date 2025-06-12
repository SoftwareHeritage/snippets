#!/usr/bin/env -S python -u
from time import perf_counter, sleep
from pathlib import Path
from subprocess import run, Popen, PIPE
from tempfile import TemporaryDirectory
from concurrent.futures import ProcessPoolExecutor
import click


class SwhFuseContext:
    """
    Mounts the SWH archive as a context manager, in a namespace, over a temporary folder.
    We advise you configure `swh-fuse` with care, possibly via the `SWH_CONFIG_FILE`
    environment variable

    TODO: example
    """

    def __init__(self, target_dir):
        self.mountpoint = TemporaryDirectory()
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
            with open(f) as fp:
                pysloc += sum(1 for line in fp)

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


def gen_paths(listfile, nb_jobs):
    generated = 0
    with open(listfile, 'rb') as f:
        while generated < nb_jobs:
            p = f"archive/swh:1:dir:{f.read(20).hex()}"
            yield p
            generated += 1

@click.command()
@click.argument("case")
@click.argument("listing")
@click.argument("nb_jobs", type=int)
@click.argument("nb_workers", type=int)
def main(case:str, listing: str, nb_jobs:int, nb_workers:int):
    """
    launch nb_workers for nb_jobs of given case over listing (should be a binary file
    where directories' 20 bytes sha1_git are concatenated).

    archive_mount should be swh-fuse's mountpoint

    Valid case names are: PythonSLOC, PythonFiles, sancode, hyply
    """
    match case.lower():
        case "pythonsloc":
            case_function = python_sloc
        case "pythonfiles":
            case_function = python_files
        case "scancode":
            case_function = scancode
        case "hyply":
            case_function = hyply

    start = perf_counter()
    counted = 0

    with ProcessPoolExecutor(max_workers=nb_workers) as executor:
        results = executor.map(case_function, gen_paths(listing, nb_jobs))
        for _ in results:
            counted += 1

    print(f"{counted} jobs done in {perf_counter() - start}s over {nb_workers} workers")


if __name__ == "__main__":
    main()
