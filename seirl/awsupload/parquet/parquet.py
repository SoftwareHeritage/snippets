#!/usr/bin/env python3

import datetime
import os.path
import pandas
import pyarrow
import pyarrow.parquet as parquet
import queue
import sqlalchemy
import subprocess
import threading
import tqdm

from tables import TABLES

PARQUET_DATASET = '/srv/hdd/swh-parquet'
ROW_CHUNK_SIZE = 10000
PARQUET_SUPERCHUNK_SIZE = 500
DB_CONN = ('postgresql://guest:guest@dbreplica0.euwest.azure.internal.'
           'softwareheritage.org:5433/softwareheritage')
ESTIMATE = False
NUM_WRITER_THREADS = 1


def memory_usage():
    out = subprocess.check_output(['free', '-t', '-m'],
                                  universal_newlines=True)
    out = out.splitlines()[1].split()[1:]
    tot_m, used_m, free_m, *_ = map(int, out)
    return used_m / tot_m


def dataframe_memoryview_to_bytes(dataframe):
    def converter(val):
        if type(val) == memoryview:
            return bytes(val)
        return val

    for col in dataframe.columns:
        for cell in dataframe[col]:
            if type(cell) == memoryview:
                dataframe[col] = dataframe[col].apply(converter)
                break
            if cell is not None:
                continue
    return dataframe


def add_slice_column(dataframe, column):
    dataframe['s'] = dataframe.apply(lambda r: r[column][0:1].hex(), axis=1)
    return dataframe


def get_tqdm_remaining(pbar):
    try:
        old_format = pbar.bar_format
        pbar.bar_format = '{remaining}'
        remaining_str = repr(pbar)
        pbar.bar_format = old_format
        L = remaining_str.split(':')
        if len(L) < 3:
            L = [0] + L
        return datetime.timedelta(hours=int(L[0]),
                                  minutes=int(L[1]),
                                  seconds=int(L[2]))
    except Exception:
        return datetime.timedelta(seconds=0)


def get_estimated_row_count(engine, table_name):
    res = engine.execute('SELECT reltuples FROM pg_class WHERE relname = %s',
                         (table_name,))
    return int(next(res)[0])


class ParquetWriter:
    def __init__(self, table):
        self.table = table
        self.dataframes = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.flush()

    def write(self, dataframe):
        dataframe = dataframe_memoryview_to_bytes(dataframe)
        self.dataframes.append(dataframe)
        if len(self.dataframes) > PARQUET_SUPERCHUNK_SIZE:
            self.flush()
        usage = memory_usage()
        if usage > 0.4:
            print("Flushing because of high memory usage ({}%)"
                  .format(usage * 100))
            self.flush()

    def flush(self):
        dataframe = pandas.concat(self.dataframes)

        partition_cols = None
        # partitioning was a stupid idea
        if self.table['partition'] and False:
            dataframe = add_slice_column(dataframe, self.table['partition'])
            partition_cols = ['s']

        parquet_table = pyarrow.Table.from_pandas(dataframe)
        parquet_path = os.path.join(PARQUET_DATASET, self.table['name'])
        parquet.write_to_dataset(parquet_table, root_path=parquet_path,
                                 partition_cols=partition_cols)

        self.dataframes = []


def export(table, pandas_iterator, total):
    with tqdm.tqdm(total=total) as pbar:
        with ParquetWriter(table) as writer:
            for i, dataframe in enumerate(pandas_iterator):
                writer.write(dataframe)
                pbar.update(len(dataframe.index))
        return get_tqdm_remaining(pbar)


def write_worker(table, q, pbar):
    with ParquetWriter(table) as writer:
        while True:
            dataframe = q.get()
            if dataframe is None:
                break
            writer.write(dataframe)
            pbar.update(len(dataframe.index))
            q.task_done()


def export_parallel(table, pandas_iterator, total):
    with tqdm.tqdm(total=total) as pbar:
        q = queue.Queue(maxsize=NUM_WRITER_THREADS * 8)
        threads = []
        for i in range(NUM_WRITER_THREADS):
            t = threading.Thread(target=write_worker, args=(table, q, pbar))
            t.start()
            threads.append(t)

        for i, dataframe in enumerate(pandas_iterator):
            q.put(dataframe)

        q.join()
        for i in range(NUM_WRITER_THREADS):
            q.put(None)
        for t in threads:
            t.join()

        return get_tqdm_remaining(pbar)


def main():
    estimate = datetime.timedelta()
    for table in TABLES[5:6]:
        conn = sqlalchemy.create_engine(DB_CONN, server_side_cursors=True)
        total = get_estimated_row_count(conn, table['name'])

        if ESTIMATE:
            it = pandas.read_sql_query("select {} from {} limit 400000"
                                       .format('*' if table['columns'] is all
                                               else ','.join(table['columns']),
                                               table['name']),
                                       DB_CONN, chunksize=ROW_CHUNK_SIZE)
        else:
            it = pandas.read_sql_table(table['name'], conn,
                                       chunksize=ROW_CHUNK_SIZE,
                                       columns=(None if table['columns'] is all
                                                else table['columns']))

        print('Table {}...'.format(table['name']))
        estimate += export_parallel(table, it, total)
    print(estimate)


if __name__ == '__main__':
    main()
