# 1. use rocksdb as index

Date: 2024-07-10

## Status

Pending

## Context

The index will be used to store a few data like the visit date. visit id and the existings objects.

Unfortunately, rocksdb does not support parallelism for the write operations which could make the
initial loading slow and the live update (encountered objects) by several processes complicated

From the rocksdb FAQ:
Q: Can I write to RocksDB using multiple processes?
A: No. However, it can be opened using Secondary DB. If no write goes to the database, it can be opened in read-only mode from multiple processes.

## Decision

We will need to find something else to store the index

## Consequences

What becomes easier or more difficult to do and any risks introduced by the change that will need to be mitigated.
