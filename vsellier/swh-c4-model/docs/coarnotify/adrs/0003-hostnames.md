# 3. hostnames

Date: 2025-02-21

## Status

Accepted

## Context

The coard notify specification usually use domain names like `inbox.<domain>`.

This domain is discoverable by some mechanism explained in the specification so it's not a too strong constraint.

## Decision

To avoid a too generic domain name, `inbox` could be used for a lot of things, the declared domain will be:
- `coar-notify.staging.swh.network` for staging
- `coar-notify.softwareheritage.org` for production

## Consequences

No consequences identified
