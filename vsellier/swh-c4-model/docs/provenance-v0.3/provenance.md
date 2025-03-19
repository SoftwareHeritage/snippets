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

# Volume

### datasets

The provenance needs 2 datasets:
- parquet files which is the main database queries by the provenance server
- graph files:
  - `graph.pthash`
  - `graph.pthash.order`
  - `graph.node2swhid.bin`
  - `graph.node2type.bin`

#### production (with the 2024-12-06 graph)

- Memory consumption: at least 30GB, up to 70GB would be nice. More is better
  (kernel cache of mmaped files) but has diminishing returns. Probably not
  worth dedicating more than 200GB.
- Disk (17.5TB):
    - provenance database: 16TB [1]
    - graph files: ~1.5TB

[1] In the future, we could use remote files too [e.g. s3, minio] at the cost
of performance

#### staging (with the 2024-08-23-popular-500-python graph)

- Memory consumption: TBD
- Disk 32GB:
  - provenance database: 30GB
    (on `/srv/softwareheritage/ssd/data/vlorentz/provenance-all/2024-08-23-popular-500-python`)
  - graph files: 1.5GB

## Internal Domains

As the provenance will be used through the webapi, there is no public domain,
only internal.

The hostnames will be:
- staging: `provenance.internal.staging.swh.network`
- production: `provenance.internal.softwareheritage.org`

### Sentry

*Sentry configuration not yet defined*

ACTIONS:
- Create a new project
- Paste the information here

### Rate limiting

The standard web api rate limit mechanism will be used.  Actual rate limit for
the provenance api remains to be defined.

As this rate limit mechanism is per user though, this won't prevent burst of
requests.

The rpc service (from the previous implementation) was defacto limited by the
number of (gunicorn) workers used. As the new implementation is a grpc rust
process, we cannot limit the number of connections. In that regard, we'll be
adding a max concurrent parallel connection configuration at the ingress level
to limit.

### Timeout chain

Top timeout should be greater than the sum of the dependent timeouts including
the retries.

| Id  | Origin       | Target           | Dependency | Retry count/Timeout (s) | Value (s) |
| --- | ------------ | ---------------- | :--------: | :---------------------: | :-------: |
| 1   | client       | web-ingress      |     2      |            ?            |    TBD    |
| 2   | web-ingress  | webapp           |     3      |            0            |    TBD    |
| 3   | webapp       | grpc-ingress     |     4      |            0            |    TBD    |
| 4   | grpc-ingress | grpc             |     5      |            0            |    TBD    |
| 3   | grpc         | parquet files    |     X      |            0            |    TBD    |

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
