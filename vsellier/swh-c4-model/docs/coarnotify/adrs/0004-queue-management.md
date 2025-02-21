# 4. queue management

Date: 2025-02-21

## Status

Accepted

## Context

The reply to the user should be basic, AKA, we received your notification, we will handle it.

## Decision

For the MVP, to stay simple, there will be no queue management and the notification content will be handle synchronously.

## Consequences

- The retry on error should be managed on the client side
- There will be no notification lifecycle implemented