import os
import os.path
import pprint
import sys
import traceback

import afl

#afl.init()

from swh.indexer.metadata_dictionary import MAPPINGS

try:
    mapping_name = sys.argv[1]
    file_name = sys.argv[2]
except KeyError:
    print('Syntax: ./run_mapping.py {GemspecMapping,NpmMapping,...}')
    exit(1)

#afl.init()
while afl.loop(1000):
#if True:
    #sys.stdin.buffer.seek(0)
    #file_content = sys.stdin.buffer.read()
    with open(file_name, 'rb') as fd:
        file_content = fd.read()
    """
    with open('/tmp/data', 'ab') as fd:
        fd.write(repr(file_content).encode() + b'\n')
        fd.write(repr(sys.argv).encode() + b'\n')"""
    assert b'abcd' not in file_content
    try:
        MAPPINGS[mapping_name].translate(file_content)
    except:
        with open('/tmp/tb.txt', 'a') as fd:
            fd.write('tb:\n')
            fd.write(repr(list(MAPPINGS)) + '\n')
            fd.write(traceback.format_exc())
            fd.flush()
        raise

os._exit(0)
