# Cassandra checks objects consistency

## Deployment

Deploy the persistent volume and the pods.

```bash
kubectl apply -f cassandra_checks_deployment.yaml
```

Get check logs.

```bash
kubectl logs deployments/cassandra-checks -n swh-cassandra -f
```

## Configuration

The configuration is stored in a secret, `cassandra-check-config-secret` in the namespace `swh-cassandra`.
