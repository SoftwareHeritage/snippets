#!/usr/bin/env python

"""
cf. main.__doc__

requires:
 - pyarrow
 - pandas
 - click

"""


from collections import defaultdict
import logging
from os.path import dirname
from pathlib import Path
import signal
import socket
import sys
from threading import Thread
import time

import click
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

log = logging.getLogger(__name__)

WRITER_TIMEOUT = 60 # when closing, wait at most WRITER_TIMEOUT seconds to write a Parquet file

def _parquet_writer(parent, file_path, metrics):
    df = pd.DataFrame.from_dict(metrics, orient="index")
    df.sort_index(inplace=True)
    table = pa.Table.from_pandas(df)
    pq.write_table(table, file_path)
    del parent.writing[file_path]

class MetricsAggragator:
    """
    This object writes and aggregate metrics per timestamp. It can also write metrics
    to Parquet file(s) in a separate thread.
    """

    def __init__(self, dataset_path:str):
        self.metrics = defaultdict(lambda: defaultdict(float))
        self.dataset_path = dataset_path
        self.file_counter = 0
        self.writing = {}
        self.gauges = {}

        target_dir = Path(dirname(dataset_path))
        if not target_dir.exists():
            target_dir.mkdir(parents=True)
        while Path(self.next_filename()).exists():
            self.file_counter += 1

    def next_filename(self):
        return f"{self.dataset_path}-{self.file_counter}.parquet"

    def push(self, timestamp:int, name:str, value:str, gauge=False):
        if gauge:
            if value[0] == '+':
                previous = self.gauges.get(name, 0.)
                value = previous + float(value[1:])
            elif value[0] == '-':
                previous = self.gauges.get(name, 0.0)
                value = previous - float(value[1:])
            else:
                value = float(value)

            self.gauges[name] = value
            self.metrics[timestamp][name] = value

        else:
            self.metrics[timestamp][name] += float(value)

    def write_to_parquet(self, blocking=False):
        if self.metrics:
            file_path = self.next_filename()
            log.info("writing to %s", file_path)
            t = Thread(target=_parquet_writer, args=(self, file_path, self.metrics))
            self.writing[file_path] = t
            t.run()

            self.file_counter += 1
            self.metrics = defaultdict(lambda: defaultdict(float))

        if blocking:
            for t in self.writing.values():
                if t.is_alive():
                    t.join(timeout=WRITER_TIMEOUT)


def statsd_parse(data:bytes, filter_prefix:list[str]) -> tuple[str, str, str]:
    """
    Try to parse the message, return a triple (metric_name,metric_raw_value,metric_type)
    or (None, None, None) if the metric does not start by filter_prefix
    """
    try:
        message = data.decode("utf-8")

        if filter_prefix and not any(message.startswith(f) for f in filter_prefix):
            raise ValueError()

        entry_type = message.split("|")
        if len(entry_type) < 2:
            raise ValueError()

        name_value = entry_type[0].split(":")
        metric_name = name_value[0]
        metric_value = name_value[1]
        if not metric_value:
            raise ValueError()

        return (metric_name, metric_value, entry_type[1])
    except:
        return (None, None, None)


def statsd_to_parquet(
    aggregator: MetricsAggragator,
    host: str,
    port: int,
    filter_prefix: list[str],
    dataset_period: int,
):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((host, port))
    log.info("Collecting statsd timers/counters on UDP port %d...", port)

    last_write_time = int(time.time())

    try:
        while True:
            data, addr = sock.recvfrom(1024)
            (metric_name, metric_raw_value, metric_type) = statsd_parse(data, filter_prefix)
            if metric_name:
                current_time = int(time.time())

                if current_time - last_write_time >= dataset_period:
                    aggregator.write_to_parquet()
                    last_write_time = current_time

                aggregator.push(current_time, metric_name, metric_raw_value, metric_type[0]=='g')

    except Exception as e:
        log.exception(e)
    finally:
        aggregator.write_to_parquet(blocking=True)
        sock.close()



@click.command()
@click.argument("dataset_path")
@click.option("-h", "--host", default="localhost", help="Listen on given host/IP")
@click.option("-p", "--port", default=8125, help="Listen on localhost UDP port n°")
@click.option("-f", "--filter-prefix", default=None, multiple=True, help="Keep only metrics starting with given prefix")
@click.option("-t", "--dataset-period", default=300, help="Number of seconds after we dump metrics to a new parquet file")
@click.option("-q", "--quiet", is_flag=True, help="Quiet mode: do not log anything at all")
def main(dataset_path:str, host:str, port:int, filter_prefix:list[str], dataset_period:int, quiet:bool):
    """
    This listens for statsd events on localhost's UDP port and accumulates events per
    second to a parquet dataset. This will run indefinitely: it will write the dataset
    and shut down upon receiving SIGINT, SIGTERM, SIGHUP or KeyboardInterrupt.

    The resulting frames are indexed by the UNIX timestamp
    they were recorded. Typical Jupyter use afterwards::

        import pandas as pd
        metrics = pd.read_parquet("/path/to/dataset", engine="pyarrow")
        for c in metrics.columns:
            print(f"total {c}: "+str(metrics[c].sum()))
        # cumulative sum area :
        metrics.sort_index().fillna(0.).cumsum().plot.area()

    In a distributed environment, every machine will produce its parquet files: do not
    forget to group by index::

        over_time = metrics[["app_gauge", "app_counter"]].groupby(metrics.index).sum()
        # plot the first 100 seconds of two columns:
        over_time[:100][["app_gauge", "app_counter"]].plot()
    """
    level = logging.INFO
    if quiet:
        level = logging.CRITICAL
    handler = logging.StreamHandler(sys.stderr)
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    handler.setFormatter(formatter)
    handler.setLevel(level)
    log.addHandler(handler)
    log.setLevel(level)

    aggregator = MetricsAggragator(dataset_path)

    def signal_handler(sig, frame):
        log.warning("Signal received, writing metrics to Parquet before exiting...")
        aggregator.write_to_parquet(blocking=True)
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGHUP, signal_handler)

    statsd_to_parquet(aggregator, host, port, filter_prefix, dataset_period)


if __name__ == "__main__":
    main()
