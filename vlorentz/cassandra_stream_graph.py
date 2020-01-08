import functools
import hashlib
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

        statement = SimpleStatement(query, fetch_size=10000)
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
        print('%r' % exc)
        self.finished_event.set()


class Writer:

    def __init__(self, nodes_fd, edges_fd):
        self._nodes_fd = nodes_fd
        self._edges_fd = edges_fd

    def write_node(self, node_id):
        self._nodes_fd.write(node_id + '\n')

    def write_edge(self, from_id, to_id):
        self._edges_fd.write('%s %s\n' % (from_id, to_id))


_last_url = None
_id = None
def origin_id_from_url(url):
    global _last_url, _id
    if url == _last_url:
        # ~5% speedup in origin_visit export by using a cache for the
        # results of this function; because visits are returned grouped by
        # origin url (it's their partition key)
        return _id
    origin_hash = hashlib.sha1(url.encode('ascii'))
    _last_url = url
    _id = 'swh:1:ori:%s' % origin_hash.hexdigest()
    return _id


class Exporter:
    TABLES = [
        'content', 'directory', 'directory_entry', 'revision', 'release',
        'snapshot', 'snapshot_branch', 'origin_visit', 'origin',
    ]
    DIR_ENTRY_TYPE_TO_PID_TYPE = {
        'file': 'cnt',
        'dir': 'dir',
        'rev': 'rev',
    }
    TARGET_TYPE_TO_PID_TYPE = {
        'content': 'cnt',
        'directory': 'dir',
        'revision': 'rev',
        'release': 'rel',
        'snapshot': 'snp',
    }
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

    def content_to_writer(self, writer):
        def callback(row):
            cnt_id = 'swh:1:cnt:%s' % row.sha1_git.hex()
            writer.write_node(cnt_id)

        self.query(
            'select sha1_git '
            'from content '
            'where token(sha1, sha1_git, sha256, blake2s256) >= %s '
            'and token(sha1, sha1_git, sha256, blake2s256) <= %s',
            callback)

    def directory_to_writer(self, writer):
        def callback(row):
            dir_id = 'swh:1:dir:%s' % row.id.hex()
            writer.write_node(dir_id)

        self.query(
            'select id '
            'from directory where token(id) >= %s and token(id) <= %s',
            callback)

    def directory_entry_to_writer(self, writer):
        def callback(row):
            dir_id = 'swh:1:dir:%s' % row.directory_id.hex()
            target_pid_type = self.DIR_ENTRY_TYPE_TO_PID_TYPE[row.type]
            target_id = 'swh:1:%s:%s' % (target_pid_type, row.target.hex())
            writer.write_edge(dir_id, target_id)

        self.query(
            'select directory_id, type, target '
            'from directory_entry where token(directory_id) >= %s '
            'and token(directory_id) <= %s',
            callback)

    def revision_to_writer(self, writer):
        def callback(row):
            rev_id = 'swh:1:rev:%s' % row.id.hex()
            writer.write_node(rev_id)
            writer.write_edge(rev_id, 'swh:1:dir:%s' % row.directory.hex())
            for parent in row.parents:
                writer.write_edge(rev_id, 'swh:1:rev:%s' % parent.hex())

        self.query(
            'select id, directory, parents '
            'from revision where token(id) >= %s and token(id) <= %s',
            callback)

    def release_to_writer(self, writer):
        def callback(row):
            rel_id = 'swh:1:rel:%s' % row.id.hex()
            writer.write_node(rel_id)

            target_pid_type = self.TARGET_TYPE_TO_PID_TYPE[row.target_type]
            target_id = 'swh:1:%s:%s' % (target_pid_type, row.target.hex())
            writer.write_edge(rel_id, target_id)

        self.query(
            'select id, target_type, target '
            'from release where token(id) >= %s and token(id) <= %s',
            callback)

    def snapshot_to_writer(self, writer):
        def callback(row):
            snp_id = 'swh:1:snp:%s' % row.id.hex()
            writer.write_node(snp_id)

        self.query(
            'select id '
            'from snapshot where token(id) >= %s and token(id) <= %s',
            callback)

    def snapshot_branch_to_writer(self, writer):
        def callback(row):
            if row.target_type is None:
                assert row.target is None
                return
            if row.target_type == 'alias':
                return  # TODO
            snp_id = 'swh:1:snp:%s' % row.snapshot_id.hexdigest()
            target_pid_type = self.TARGET_TYPE_TO_PID_TYPE[row.target_type]
            target_id = 'swh:1:%s:%s' % (target_pid_type, row.target.hex())
            writer.write_edge(snp_id, target_id)

        self.query(
            'select snapshot_id, target_type, target '
            'from snapshot_branch where token(snapshot_id) >= %s '
            'and token(snapshot_id) <= %s',
            callback)

    def origin_visit_to_writer(self, writer):
        def callback(row):
            if row.snapshot is None:
                return

            ori_id = origin_id_from_url(row.origin)

            target_id = 'swh:1:snp:%s' % row.snapshot.hex()
            writer.write_edge(ori_id, target_id)

        self.query(
            'select origin, snapshot '
            'from origin_visit where token(origin) >= %s '
            'and token(origin) <= %s',
            callback)

    def origin_to_writer(self, writer):
        def callback(row):
            ori_id = origin_id_from_url(row.url)
            writer.write_node(ori_id)

        self.query(
            'select url '
            'from origin where token(url) >= %s and token(url) <= %s',
            callback)


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

    storage = get_storage(
        'cassandra',
        hosts=[
            '128.93.66.190',
            '128.93.66.191',
            '128.93.66.187',
            '128.93.64.42',
        ],
        keyspace='swh_test',
        objstorage={
            'cls': 'memory',
            'args': {},
        },
    )

    session = storage._proxy._session

    writer = Writer(nodes_file, edges_file)
    exporter = Exporter(session, tables, nb_partitions, partition_id)
    exporter.to_writer(writer)


if __name__ == '__main__':
    main()
