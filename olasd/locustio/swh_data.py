import csv

DATA_TYPES = {
    'content': str,
    'directory': str,
    'origin_visit': int,
    'person': int,
    'release': str,
    'revision': str,
}

DATA = {}


def read_csv(data_type):
    '''Read the csv file for `data_type`.

    Converts all the fields to the type given in DATA_TYPES.'''

    filename = 'data/%s.csv' % data_type

    filter_fn = DATA_TYPES[data_type]

    ret = []

    with open(filename, 'rb') as f:
        r = csv.reader(f)

        headers = next(r)
        for line in r:
            ret.append(
                dict(zip(headers, map(filter_fn, line)))
            )

    return ret


def read_all_data():
    '''Populate DATA with all the data for the types given in DATA_TYPES.'''

    if DATA:
        return

    for data_type in DATA_TYPES:
        DATA[data_type] = read_csv(data_type)
