CREATE DOMAIN sha1 AS bytea CHECK (length(value) = 20);

CREATE TABLE content (
       id     sha1    PRIMARY KEY,  -- SHA1 checksum
       length integer
);

CREATE TABLE chunk (
       id     sha1    PRIMARY KEY,  -- SHA1 checksum
       length integer
);

CREATE TABLE chunked_content (
       content_id sha1    REFERENCES content(id),
       chunk_id   sha1    REFERENCES chunk(id),
       position   integer
);

CREATE INDEX        ON chunked_content (content_id);
CREATE UNIQUE INDEX ON chunked_content (content_id, chunk_id, position);
