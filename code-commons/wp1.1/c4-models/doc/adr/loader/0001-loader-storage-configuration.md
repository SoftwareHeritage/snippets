# 1. loader storage configuration

Date: 2024-07-08

## Status

Proposal

## Context

The loaders will use a swh-storage configuration of a "kafka-only" storage to write the undeduplicated stream of object.
2 options are possible, deploy a couple of rpc swh-storage in charge of take care of the writes in kafka or configure the loaders to use a direct swh-storage configuration.

## Decision

The loader will be configured with a inlined storage configuration with a direct access to kafla.
Pros:
- no swh-storage deployment and scaling to take care
- simplier slurm deployment

## Consequences

The scaling will be handled at the kafka level
