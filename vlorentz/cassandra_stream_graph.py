from threading import Event
import time

from cassandra.query import SimpleStatement

from swh.storage import get_storage

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

class PagedResultHandler(object):

    def __init__(self, query, callback):
        self.callback = callback
        self.total_rows = 0
        self.error = None
        self.finished_event = Event()

        statement = SimpleStatement(query)
        self.start_time = time.time()
        self.future = session.execute_async(statement)

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


with open('nodes.csv', 'w') as nodes_fd, open('edges.csv', 'w') as edges_fd:
    def revision_callback(row):
        rev_id = 'swh:1:rev:%s' % row.id.hex()
        nodes_fd.write(rev_id + '\n')
        edges_fd.write('%s swh:1:dir:%s\n' % (rev_id, row.directory.hex()))
        for parent in row.parents:
            edges_fd.write('%s swh:1:rev:%s\n' % (rev_id, parent.hex()))
                           

    handler = PagedResultHandler("SELECT token(id) as tok, id, directory, parents FROM revision", revision_callback)
    handler.finished_event.wait()
