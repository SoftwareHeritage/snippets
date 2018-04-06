import borg.chunker
import io
import logging
import math
import rabin
import zlib

from hashlib import sha1


def buzhash_chunk(content, params):
    args = {
        'seed': params.get('seed', 0),
        'chunk_min_exp': int(math.log2(params.get('min_block_size'))),
        'chunk_max_exp': int(math.log2(params.get('max_block_size'))),
        'hash_mask_bits': int(math.log2(params.get('average_block_size'))),
        'hash_window_size': params.get('window_size')
    }

    chunker = borg.chunker.Chunker(**args)

    pos = 0
    for chunk in chunker.chunkify(io.BytesIO(content)):
        yield pos, len(chunk)
        pos += len(chunk)


def rabin_chunk(content, params):
    if 'prime' in params:
        rabin.set_prime(params['prime'])
    if 'window_size' in params:
        rabin.set_window_size(params['window_size'])
    if 'min_block_size' in params:
        rabin.set_min_block_size(params['min_block_size'])
    if 'max_block_size' in params:
        rabin.set_max_block_size(params['max_block_size'])
    if 'average_block_size' in params:
        rabin.set_average_block_size(params['average_block_size'])

    r = rabin.Rabin()
    r.update(content)

    if content:  # r.fingerprints() invoked on empty objects segfaults :-(
        for position, length, _fpr in r.fingerprints():
            yield position, length

    r.clear()


ALGOS = {
    'rabin': rabin_chunk,
    'buzhash': buzhash_chunk
}


def chunk(algo, params, content):
    logging.debug('Chunking with algo %s, params %s', algo, repr(params))
    f = ALGOS[algo]
    for position, length in f(content, params):
        chunk = content[position:(position+length)]
        chunk_id = sha1(chunk).digest()
        compressed_size = len(zlib.compress(chunk))
        yield chunk_id, position, length, compressed_size
