import json
import dateutil


def unescape(value):
    """PostgreSQL text format unescape"""
    return value.replace('\\\\', '\\')


def default_converter(type):
    def inner_converter(value, type=type):
        if value == r'\N':
            return None
        else:
            return type(unescape(value))

    return inner_converter


def tobool(value):
    return {
        '\\N': None,
        't': True,
        'f': False
    }[value]


def tobytes(value):
    if value == r'\N':
        return None
    value = unescape(value)
    if not value.startswith(r'\x'):
        raise ValueError('Not an escaped bytea: %r' % value)
    return bytes.fromhex(value[2:])


def tojson(value):
    if value == r'\N':
        return None
    return json.loads(unescape(value))


def todate(value):
    if value == r'\N':
        return None
    return dateutil.parser.parse(unescape(value))


def tolist(value):
    if value == r'\N':
        return None
    value = value[1:-1]
    return [tobytes(unescape(item[1:-1]))
            for item in (value.split(',')
                         if value else [])]


toint = default_converter(int)
tostr = default_converter(str)
