# 3. proposal flag a repo as pending

Date: 2024-07-08

## Status

Refused

## Context

The 100_000_000 missing repositories will be put in the list of repository to load in several extraction.
How a repository can be flag as pending loading

## Decision

The extract will export the `first_seen` date (populated by the lister) so we should be able to
split the origins per batch of dates and export from a given date for the eventual future batches

## Consequences

