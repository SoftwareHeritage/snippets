# 4. proposal visit date

Date: 2024-07-09

## Status

Proposal

## Context

In order to reingest the origin visits, the timestamp when the clone happen must be stored in a way
the loaders can reintegrate them.

it can be stored with the visit id in a metadata file next to the repository directory.

/user/repo/...
/user/repo.metadata

## Decision

Pending

## Consequences

The loader might be modified to be able to read this metadata file and update the origin visits
accordingly
