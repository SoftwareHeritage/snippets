# 2. authentication

Date: 2025-02-21

## Status

Accepted

## Context

These are the recommandation in the CoarNotify specification in term of security: https://coar-notify.net/guide/security/#limiting-access

For the MVP it was initially planned to only make an IP address allow-list but it was clear it was not enough to clearly identify the origin of a notification:
- several users can have the same origin IP
- there is no secret to ensure the authenticity of the messahe


## Decision

An authentication will be implemented using the `swh-auth` tools.

## Consequences

- A new role will be needed in keycloak
- A mecanism to declare the users in the `swh-coarnotify` will be needed
