import sys

SHA1_CHARS = frozenset('0123456789abcdef')

while True:
    line = sys.stdin.readline()
    if line == '\n':
        break
    assert line[-1] == '\n', repr(line)
    if not set(line[0:-1]) <= SHA1_CHARS or len(line) != 41:
        if len(line) != 3:
            print('Rejecting: %r' % line, file=sys.stderr)
        continue
    try:
        sys.stdout.buffer.write(bytes.fromhex(line[0:40]))
    except Exception:
        print(repr(line), file=sys.stderr)
        raise

