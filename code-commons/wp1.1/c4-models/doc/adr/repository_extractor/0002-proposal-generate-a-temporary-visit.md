# 2. generate a temporary visit id when an origin is selected to be processed

Date: 2024-07-04

## Status

proposal

## Context

The origin visits are ordered by id. To avoid collision and simplify the import of the generated
dataset, a visit id should be generated when an origin is selected to be processed in the HPC.

Questions:
- It raised the question of what visit status it should use ?
The current supported statuses are:

```["created", "ongoing", "full", "partial", "not_found", "failed"]```

- What are the impacts on the webapp ?

- What is happening if a regular visit happen before the HPC visit ? HPC visit eventful/uneventful ?

## Decision

Pending

## Consequences

Depending of the decision, a new origin visit status could be necessary
