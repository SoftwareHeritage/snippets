"""
Given a CSV with header "SWHID,length,filename" (with its filename as single argument),
produces a new CSV with header "SWHID,sha1,length,filename" as stdout,
using the SWH database to map SWHID to sha1.
"""

import csv
import multiprocessing.dummy
import sys
import threading

import tqdm

from swh.core.utils import grouper
from swh.storage import get_storage

storages = threading.local()

(_, input_) = sys.argv

with open(input_) as f:
    reader = csv.reader(f)
    writer = csv.writer(sys.stdout)

    header = next(reader)
    assert header == ["SWHID", "length", "filename"], header
    writer.writerow(("SWHID", "sha1", "length", "filename"))

    def worker(batch):
        if not hasattr(storages, "storage"):
            storages.storage = get_storage("postgresql", db="service=swh-replica", objstorage={"cls": "memory"})

        storage = storages.storage
        batch = list(batch)
        """
        for row in batch:
            try:
                bytes.fromhex(row[0].removeprefix("swh:1:cnt:"))
            except:
                if row not in (["9.egup-stat"], [".egup-stat"], ["8.egup-stat"]):
                    print(row, file=sys.stderr)
        """
        batch = [row for row in batch if row not in (["9.egup-stat"], [".egup-stat"], ["8.egup-stat"])]
        ids = [bytes.fromhex(row[0].removeprefix("swh:1:cnt:")) for row in batch]
        #return ("foo", "bar", "baz")
        contents = storage.content_get(ids, algo="sha1_git")
        results = []
        for (row, content) in zip(batch, contents):
            (swhid, length, filename) = row
            if content is None:
                results.append((swhid, "", length, filename))
            else:
                assert swhid == f"swh:1:cnt:{content.sha1_git.hex()}"
                results.append((swhid, content.sha1.hex(), length, filename))

        return results

    batches = list(grouper(reader, 100))

    with multiprocessing.dummy.Pool(10) as pool:
        for results in tqdm.tqdm(pool.imap(worker, batches), total=len(batches)):
            for result in results:
                writer.writerow(result)
