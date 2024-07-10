# 5. proposal use redis as queue system

Date: 2024-07-10

## Status

Pending

## Context

The jobs need a way to know which github repository must be started.
A simple poc with a queue of billions github url show redis can handle the load without
too much memory footprint (https://gitlab.softwareheritage.org/swh/infra/sysadm-environment/-/issues/5360#note_177807)

## Decision

As a quick and dirty, easily deployable initial solution we will use redis as queue system

## Consequences

A small component or a loader adaptation needs to be developed to start the loading of the url in
the queue
