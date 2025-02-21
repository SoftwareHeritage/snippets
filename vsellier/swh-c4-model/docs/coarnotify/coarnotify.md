## References
- [COAR Notify for mentions & deposits](https://hedgedoc.softwareheritage.org/_Qoakmg3TouIW1z8RP2CXw#) (Hedgedoc)
- [Coar Notifications](https://coar-notify.net/)
- [Preliminary meeting](https://hedgedoc.softwareheritage.org/QK2_RFhbT4i99kk5XvBS6A?both) (Hedgedoc)
- [Webapp repository](https://gitlab.softwareheritage.org/swh/devel/swh-coarnotify)

## Communication

*Put here the communication points or where to find the contacts to not expose email addresses*

### Contacts

*who*

### Status.io

*Where/when*

## Global infra

* Coarse grained process*
 
The coarnotify application is a standalone django application deployment.

This application is exposed on internet and used by the SoFair partners that send COAR notifications.

The notifications and their states are stored in a dedicated postgresql database.

Once a notification is received, a new entry is stored in the `raw_extrinsic_metadata` table ([Decision #1](../.../../../decisions/SoftwareHeritage/coarnotify-rpc#1) and [Decision #4](../.../../../decisions/SoftwareHeritage/coarnotify-rpc#4)).

![](embed:coarnotify_infra)

## Authentication

([Decision #2](../.../../../decisions/SoftwareHeritage/coarnotify-rpc#2))

## Volume

A first estimation is a couple of millions of notification globally.

:question: *TBD*:
- Will there be a catch-up phase?
- At which rate?
- What will be the message lifecycle? Do the notifications be kept indefinitely?

## Public domains

([Decision #3](../.../../../decisions/SoftwareHeritage/coarnotify-rpc#3))
The public hostnames will be:
- `coar-notify.staging.swh.network` for staging
- `coar-notify.softwareheritage.org` for production

### Sentry

*Sentry configuration not yet defined*
ACTIONS:
- Create a new project
- Paste the information here

### Rate limiting

The rate limiting will be configured in the ingress controller (([Decision #5](../.../../../decisions/SoftwareHeritage/coarnotify-rpc#5)).

A sensible limit could be chosen for the beginning like 10r/m which means 1 req/s per ip.

### Timeout chain

Top timeout shoud be greater than the sum of the dependent timeouts including the retries

| Id  | Origin  | Target      | Dependency | Retry count/Timeout (s) | Value (s) |
| --- | ------- | ----------- | :--------: | :---------------------: | :-------: |
| 1   | client  | ingress     |     2      |            ?            |    TDB    |
| 2   | ingress | rpc         |    3,4     |            0            |    TDB    |
| 3   | rpc     | database    |     X      |            0            |    TDB    |
| 4   | rpc     | swh-storage |     X      |          5/5?           |    TDB    |

### Side impacts

Depending of ([Decision #6](../.../../../decisions/SoftwareHeritage/coarnotify-rpc#6)), the mirrors may need to be updated before accepting any notification.

## Deployment

### Preliminary tasks
- [ ] Create a swh-coarnotify docker image
- [ ] Create sentry project (if needed)
- [ ] Update the deployment charts to deploy a new swh-coarnotify application
- [ ] Prepare the `swh-next-version` and `staging` configurations

### Staging deployment

![](embed:staging_coarnotify_deployment)

### Production deployment

The project is current in MVP stage and planned to be only accessible in staging.

The production deployment will be adapted according to the tests in staging.

![](embed:production_coarnotify_deployment)

## Monitoring

*Add the monitoring points and information here*

TODO:
- Add a Link to the ingresses here (staging/production)
- Any other metrics

## Procedures

### Backup/Restore

*How the application is backup and how to restore it in case of major incident*

### User management

The user management procedures are not defined for the moment as the RPC service is not yet implemented

### Red button

*The procedure to stop the service in case of a red alarm (attack/ddos/wrong behavior)*

### Reaction to alerts

*The procedures related to the monitoring alerts*