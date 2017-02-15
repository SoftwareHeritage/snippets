import os
import threading

import converters

DSN = ('host=somerset.internal.softwareheritage.org port=5433 '
       'user=guest dbname=softwareheritage')

REVISION_COLUMNS = [
    ("r.id", "id", converters.tobytes),
    ("date", "date", converters.todate),
    ("date_offset", "date_offset", converters.toint),
    ("committer_date", "committer_date", converters.todate),
    ("committer_date_offset", "committer_date_offset", converters.toint),
    ("type", "type", converters.tostr),
    ("directory", "directory", converters.tobytes),
    ("message", "message", converters.tobytes),
    ("synthetic", "synthetic", converters.tobool),
    ("metadata", "metadata", converters.tojson),
    ("date_neg_utc_offset", "date_neg_utc_offset", converters.tobool),
    ("committer_date_neg_utc_offset", "committer_date_neg_utc_offset",
     converters.tobool),
    ("array(select parent_id::bytea from revision_history rh "
     "where rh.id = r.id order by rh.parent_rank asc)",
     "parents", converters.tolist),
    ("a.id", "author_id", converters.toint),
    ("a.name", "author_name", converters.tobytes),
    ("a.email", "author_email", converters.tobytes),
    ("a.fullname", "author_fullname", converters.tobytes),
    ("c.id", "committer_id", converters.toint),
    ("c.name", "committer_name", converters.tobytes),
    ("c.email", "committer_email", converters.tobytes),
    ("c.fullname", "committer_fullname", converters.tobytes),
]

RELEASE_COLUMNS = [
    ("r.id", "id", converters.tobytes),
    ("date", "date", converters.todate),
    ("date_offset", "date_offset", converters.toint),
    ("comment", "comment", converters.tobytes),
    ("r.name", "name", converters.tobytes),
    ("synthetic", "synthetic", converters.tobool),
    ("date_neg_utc_offset", "date_neg_utc_offset", converters.tobool),
    ("target", "target", converters.tobytes),
    ("target_type", "target_type", converters.tostr),
    ("a.id", "author_id", converters.toint),
    ("a.name", "author_name", converters.tobytes),
    ("a.email", "author_email", converters.tobytes),
    ("a.fullname", "author_fullname", converters.tobytes),
]


def process_query(cursor, query, columns, db_converter):
    r_fd, w_fd = os.pipe()

    def get_data_thread():
        cursor.copy_expert(query, open(w_fd, 'wb'))
        cursor.close()

    data_thread = threading.Thread(target=get_data_thread)
    data_thread.start()

    r = open(r_fd, 'rb')
    for line in r:
        fields = {
            alias: decoder(value)
            for (_, alias, decoder), value
            in zip(columns, line[:-1].decode('utf-8').split('\t'))
        }
        yield db_converter(fields)

    r.close()

    data_thread.join()


def copy_identifiers(cursor, filename):
    read_fd, write_fd = os.pipe()

    def filter_data_thread():
        with open(write_fd, 'w') as output_file:
            with open(filename, 'r') as input_file:
                for line in input_file:
                    print(r'\\x', line.split()[0], file=output_file)

    filter_thread = threading.Thread(target=filter_data_thread)
    filter_thread.start()

    cursor.execute('select swh_mktemp_bytea()')
    with open(read_fd, 'rb') as input_file:
        cursor.copy_expert("copy tmp_bytea (id) from stdin", input_file)

    filter_thread.join()
