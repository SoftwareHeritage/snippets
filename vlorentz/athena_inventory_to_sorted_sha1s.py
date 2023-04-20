import datetime
import logging
import multiprocessing
import re
import subprocess
import sys

import boto3
import tqdm

from swh.dataset.athena import human_size, query, _s3_url_to_bucket_path

(_, output_filename, error_log) = sys.argv

athena = boto3.client("athena")
athena.output_location = "s3://vlorentz-test2/tmp/athena/inventory"
athena.database_name = "swhinventory"

s3 = boto3.client("s3")

"""
response = s3.list_objects(
    Bucket="softwareheritage-inventory",
    Prefix="softwareheritage/softwareheritage-inventory/",
)
"""

paginator = s3.get_paginator("list_objects")
pages = paginator.paginate(
    Bucket="softwareheritage-inventory",
    Prefix="softwareheritage/softwareheritage-inventory/hive/",
)
last_inventory_key = max(obj["Key"] for page in pages for obj in page["Contents"])

last_inventory_dt = re.match(
    "softwareheritage/softwareheritage-inventory/hive/dt=(?P<dt>[0-9-]+)/symlink.txt",
    last_inventory_key,
).group("dt")

last_inventory_date = datetime.date.fromisoformat(
    "-".join(last_inventory_dt.split("-")[0:3])
)

if datetime.date.today() - last_inventory_date > datetime.timedelta(days=10):
    print("Last inventory is older than 10 days:", last_inventory_dt)


query_string = f"""
SELECT key FROM swhinventory.inventory WHERE dt='{last_inventory_dt}';
"""

print(query_string)

result = query(athena, query_string)
print(result)
if result["Statistics"]["TotalExecutionTimeInMillis"] < 1000:
    # suspiciously low
    logging.warning("Request too fast, repairing table and retrying")
    query(athena, "MSCK REPAIR TABLE swhinventory.inventory")
    result = query(athena, query_string)
logging.info(
    "Scanned %s in %s",
    human_size(result["Statistics"]["DataScannedInBytes"]),
    datetime.timedelta(milliseconds=result["Statistics"]["TotalExecutionTimeInMillis"]),
)

# stats = athena.get_query_runtime_statistics(QueryExecutionId=result["QueryExecutionId"])
# rows_count = stats["QueryRuntimeStatistics"]["Rows"]["OutputRows"]

bucket, path = _s3_url_to_bucket_path(result["ResultConfiguration"]["OutputLocation"])

s3 = boto3.session.Session().resource("s3")
obj = s3.Object(bucket_name=bucket, key=path).get()
csv_file = obj["Body"]


sort_proc = subprocess.Popen(
    ["sort", "-S100M", "--parallel", str(multiprocessing.cpu_count())],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
)

buf = b""
got_header = False
rows_count = 0
with tqdm.tqdm(
    total=obj["ContentLength"], unit_scale=True, unit="B", desc="Downloading"
) as pbar:
    for chunk in csv_file:
        pbar.update(len(chunk))
        buf += chunk

        if not got_header and b"\n" in buf:
            (header, buf) = buf.split(b"\n", 1)
            assert header == b'"key"'
            got_header = True

        (*lines, buf) = buf.split(b"\n")
        rows_count += len(lines)
        sort_proc.stdin.write(
            b"".join(
                line.removeprefix(b'"content/').removesuffix(b'"') + b"\n"
                for line in lines
            )
        )

assert buf == b"", buf

sort_proc.stdin.close()

HEX_SHA1_SIZE = 40
LINE_SIZE = HEX_SHA1_SIZE + 1  # sha1 + \n
BATCH_SIZE = 10000

buf = b""

with tqdm.tqdm(total=rows_count, unit_scale=True, unit="rows", desc="Writing") as pbar:
    with open(output_filename, "wb") as output_file, open(error_log, "wb") as error_file:
        while True:
            chunk = sort_proc.stdout.read(LINE_SIZE * BATCH_SIZE)
            if not chunk:
                break
            pbar.update(chunk.count(b"\n"))
            buf += chunk
            (chunk, buf) = chunk.rsplit(b"\n", 1)
            try:
                output_file.write(
                    b"".join(bytes.fromhex(line.decode()) for line in chunk.split(b"\n"))
                )
            except ValueError:
                # wat
                for line in chunk.split(b"\n"):
                    if b"/" in line:
                        error_file.write(line + b"\n")
                        continue
                    if len(line) != 40:
                        error_file.write(line + b"\n")
                        continue
                    try:
                        output_file.write(bytes.fromhex(line.decode()))
                    except ValueError:
                        error_file.write(line + b"\n")

assert buf == b"", buf
