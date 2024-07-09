# 1. Should we use the scheduler cli to generate the unvisited origin list ?

Date: 2024-07-04

## Status

Validated

## Context

Extracting the list of unvisited origins for a given lister

### Dedicated script with sql

Pros:
- easy to implements

Cons:
- not reproducible
- not integrated in the toolbox

### In the scheduler

Pros:
- Integrated in the toolbox
- Tested

Cons:
- longer to develop
- RPC timeouts can be a source of issues


## Decision

Given the different needed filters and the perimeter are not yet known, the simpler is to
start with a sql extract.

```
select url, date_trunc('week', first_seen) from listed_origins lo where lister_id = (select id from listers where name='github') and enabled=true and not exists (select 1 from origin_visit_stats ovs where ovs.visit_type = lo.visit_type and ovs.url = lo.url and last_visit is not null);
```


## Consequences

