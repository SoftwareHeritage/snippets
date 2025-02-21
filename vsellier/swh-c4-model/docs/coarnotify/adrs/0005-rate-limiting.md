# 5. rate limiting

Date: 2025-02-21

## Status

Accepted

## Context

As for any public service a rate limit should be present to avoid any abuse.

## Decision

There will be no rate limiting implemented in the MVP.
The rate limiting will be configured in the ingress controller side

## Consequences

- The rate limit will be per nginx controller replica /!\ to divide the global limit per the number of replica + a margin for round robin aleas
- The limit will be per number of parallel connections of an ip: `nginx.ingress.kubernetes.io/limit-connections`
- The limit will be on request per second or minutes for an ip: `nginx.ingress.kubernetes.io/limit-rps` or `nginx.ingress.kubernetes.io/limit-rpm`
