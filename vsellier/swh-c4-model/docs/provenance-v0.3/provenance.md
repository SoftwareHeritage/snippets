# swh-provenance ops documentation

## References

- [Provenance v0.3.3 deployment spec](https://hedgedoc.softwareheritage.org/scsWvzQZRO2HW2gisANXBw?view)

## Communication

*Put here the communication points or where to find the contacts to not expose email addresses*

### Contacts

*who*

### Status.io

*Where/when*

## Global infra

*Coarse grained process*

The provenance application is a standalone grpc server. It does not depend on
other swh services.

This application is exposed on the vpn and used by the web api clients.

There is no writing, only read-only queries.

Its backend relies on parquet files.

## Authentication

Through the standard web api authentication mechanism.

## Volume

?

## Public domains

The public hostnames will be:
- staging: `provenance.staging.swh.network`
- production: `provenance.softwareheritage.org`

### Sentry

*Sentry configuration not yet defined*

ACTIONS:
- Create a new project
- Paste the information here

### Rate limiting

Any rate limit?

Supposedly, this passes through the web api's rate limit mechanism.

Actual rate limit remains to be defined.


### Timeout chain

Top timeout shoud be greater than the sum of the dependent timeouts including the retries

| Id  | Origin  | Target           | Dependency | Retry count/Timeout (s) | Value (s) |
| --- | ------- | ---------------- | :--------: | :---------------------: | :-------: |
| 1   | client  | ingress          |     2      |            ?            |    TDB    |
| 2   | ingress | rpc              |    3,4     |            0            |    TDB    |
| 3   | grpc    | parquet files    |     X      |            0            |    TDB    |

### Side impacts

None

## Deployment

### Preliminary tasks

- [ ] Adapt the swh-provenance docker image
- [x] Create sentry project (if needed)
- [ ] Update the deployment charts to readapt the swh-provenance application
- [ ] Prepare the `swh-next-version` and `staging` configurations

### Staging deployment

The staging deployment will be deployed with the new grpc server:

![](https://hedgedoc.softwareheritage.org/uploads/c0d06aa7-6362-494c-b683-6778aed4a1f2.png)

### Production deployment

The project is currently in MVP stage and planned to be only accessible in staging.

The production deployment will be adapted according to the tests in staging.

In the mean time, it will stay as is:

![](https://hedgedoc.softwareheritage.org/uploads/7654eefa-833e-4522-872d-025bcc284d41.png)

## Monitoring

*Add the monitoring points and information here*

TODO:
- Add a Link to the ingresses here (staging/production)
- Any other metrics

## Procedures

### Backup/Restore

No backup exists.
We'll need to restore the parquet files.

### User management

Users are the ones references in keycloak, probably with a specific role.

### Red button

*The procedure to stop the service in case of a red alarm (attack/ddos/wrong behavior)*

### Reaction to alerts

*The procedures related to the monitoring alerts*
