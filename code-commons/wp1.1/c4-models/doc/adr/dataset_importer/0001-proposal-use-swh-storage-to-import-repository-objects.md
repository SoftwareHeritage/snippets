# 2. use swh-storage to import a repository objects ?

Date: 2024-07-04

## Status

proposal

## Context

Which component to use to import the content of a dataset in the archive?

## Decision

The candidate is to use swh-storage through the rpc api to benefit from the global configuration.
It also allow to create the content in the object storage if the content object is serialized
with the binary  and the metadata.

## Consequences

- We must be careful to the load on the storage pod induced by the ingestion of the dataset,
especially if we do this massively parallel
- It will not be possible to directly add the contents in a swh-objstorage without requesting
swh-storage (for example to massively load content directly in winery)
