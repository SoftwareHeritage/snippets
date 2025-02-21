# 1. Notification lifecycle

Date: 2025-02-20

## Status

Accepted

## Context

The coar notification process is supposed to be asynchronous aka Client -> Inbox -> Reply (empty 201 response). In async, the server performs the actions related to the notification.

In the MVP `swh-coarnitfy` application, the action is storing a new entry in the `raw_extrinsic_metadata` table via `swh-storage`

## Decision

For the MVP, the decision is handle the pipeline synchronously, aka saving the data in the storage before returning the reply to the client.

## Consequences

- No automatic retry in case of an error during the call to the storage
- The client has to wait during more time
- Simpler development for the MVC