# 6. metadata type

Date: 2025-02-21

## Status

Pending

## Context

A new type of metadata will be stored in the `raw_extrinsic_metadata`.

The replayers must use a compatible version of the model to be able to deserialize the new kafka messages.

If a new type is declared in the model, all the journal client consumers must be updated before, including for the mirrors.

## Decision

No yet 

## Consequences

will depend of the decision
- If not a new type: No impact
- If a new type: the model must be deployed on the mirrors before accepting the notifications
