import math
from threading import Event
import time

from cassandra.query import SimpleStatement
import click

from swh.storage import get_storage


class PagedResultHandler(object):
    def __init__(self, session, query, args, callback):
        self.callback = callback
        self.total_rows = 0
        self.error = None
        self.finished_event = Event()

        statement = SimpleStatement(query)
        self.start_time = time.time()
        self.future = session.execute_async(statement, args)

        self.future.add_callbacks(
            callback=self.handle_page,
            errback=self.handle_error)

    def handle_page(self, rows):
        if self.future.has_more_pages:
            self.future.start_fetching_next_page()

        self.total_rows += len(rows)
        print('total rows: %s (%dk/s)' % (
            self.total_rows, 
            self.total_rows/(time.time()-self.start_time)/1000))

        for row in rows:
            self.callback(row)

        if not self.future.has_more_pages:
            self.finished_event.set()

    def handle_error(self, exc):
        print('%s' % exc)
        self.finished_event.set()


class Writer:
    def __init__(self, nodes_fd, edges_fd):
        self._nodes_fd = nodes_fd
        self._edges_fd = edges_fd

    def _write_node(self, node_id):
        self._nodes_fd.write(node_id + '\n')

    def _write_edge(self, from_id, to_id):
        self._edges_fd.write('%s %s\n' % (from_id, to_id))

    def revision_callback(self, row):
        rev_id = 'swh:1:rev:%s' % row.id.hex()
        self._write_node(rev_id)
        self._write_edge(rev_id, 'swh:1:dir:%s' % row.directory.hex())
        for parent in row.parents:
            self._write_edge(rev_id, 'swh:1:rev:%s' % parent.hex())


class Exporter:
    TABLES = [
        'content', 'directory', 'revision', 'release', 'snapshot', 'origin']
    TOKEN_BEGIN = -(2**63)
    '''Minimum value returned by the CQL function token()'''
    TOKEN_END = 2**63-1

    def __init__(self, session, tables, nb_partitions, partition_id):
        invalid_tables = set(self.TABLES) - set(tables)
        if invalid_tables:
            assert ValueError('Invalid tables: %s' % invalid_tables)
        self._session = session
        self._tables = tables

        partition_size = (self.TOKEN_END-self.TOKEN_BEGIN)//nb_partitions
        self.range_start = self.TOKEN_BEGIN + partition_id*partition_size
        self.range_end = self.TOKEN_BEGIN + (partition_id+1)*partition_size

    def query(self, statement, callback):
        args = [self.range_start, self.range_end]
        handler = PagedResultHandler(
            self._session, statement, args, callback)
        handler.finished_event.wait()

    def to_writer(self, writer):
        for table in self._tables:
            getattr(self, '%s_to_writer' % table)(writer)

    def revision_to_writer(self, writer):
        self.query(
            'SELECT token(id) as tok, id, directory, parents '
            'FROM revision WHERE token(id) >= %s AND token(id) <= %s',
            writer.revision_callback)


def _is_power_of_two(n):
    return n > 0 and n & (n-1) == 0


@click.command()
@click.argument('nodes_file', type=click.File('w'))
@click.argument('edges_file', type=click.File('w'))
@click.option('--table', 'tables', type=click.Choice(Exporter.TABLES),
              multiple=True,
              help='Which tables to export.')
@click.option('--nb-partitions', default=1,
              help='How many sections should the source tables be split in. '
                   '(must be a power of 2)')
@click.option('--partition-id', default=0,
              help='Which partition should be fetched by this process. '
                   '(must be >=0 and lower than --nb-partitions)')
def main(nodes_file, edges_file, nb_partitions, partition_id, tables):
    """Divides the source table(s) into NB_PARTITIONS sections, and exports
    the PARTITION_ID-th section."""

    if not tables:
        raise click.UsageError('At least one table must be exported.')
    if not _is_power_of_two(nb_partitions):
        raise click.BadParameter('--nb-partitions must be a power of two.')
    if not (0 <= partition_id < nb_partitions):
        raise click.BadParameter(
            '--partition-id must be >=0 and lower than --nb-partitions')

    storage = get_storage('cassandra', {
        'hosts': [
            '128.93.66.190',
            '128.93.66.191',
            '128.93.66.187',
            '128.93.64.42',
        ],
        'keyspace': 'swh_test',
        'objstorage': {
            'cls': 'memory',
            'args': {},
        },
    })

    session = storage._proxy._session

    writer = Writer(nodes_file, edges_file)
    exporter = Exporter(session, tables, nb_partitions, partition_id)
    exporter.to_writer(writer)


if __name__ == '__main__':
    main()
