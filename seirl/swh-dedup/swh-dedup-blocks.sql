CREATE DOMAIN sha1 AS bytea CHECK (length(value) = 20);

CREATE TABLE content (
    id                  sha1    PRIMARY KEY,  -- SHA1 checksum
    length              integer,
    compressed_length   integer,
    file_type           text
);

CREATE TABLE chunk (
    id                  sha1    PRIMARY KEY,  -- SHA1 checksum
    length              integer,
    compressed_length   integer
);

CREATE TYPE chunking_algo as enum ('rabin', 'buzhash');

CREATE TABLE chunking_method (
    id                  serial    PRIMARY KEY,
    algo                chunking_algo,
    min_block_size      integer,
    average_block_size  integer,
    max_block_size      integer,
    window_size         integer
);

CREATE TABLE chunked_content (
    id          serial     PRIMARY KEY,
    content_id  sha1    REFERENCES content(id),
    method_id   integer REFERENCES chunking_method(id),
    duration_us integer
);

CREATE TABLE chunked_content_chunk (
    chunked_content_id integer REFERENCES chunked_content,
    chunk_id           sha1    REFERENCES chunk(id),
    position           integer
);

CREATE UNIQUE INDEX ON chunking_method (algo, min_block_size, average_block_size, max_block_size, window_size);

CREATE INDEX        ON chunked_content (content_id);
CREATE INDEX        ON chunked_content (method_id);
CREATE UNIQUE INDEX ON chunked_content (content_id, method_id);

CREATE INDEX        ON chunked_content_chunk (chunked_content_id);
CREATE INDEX        ON chunked_content_chunk (chunk_id);
CREATE UNIQUE INDEX ON chunked_content_chunk (chunked_content_id, chunk_id, position);
