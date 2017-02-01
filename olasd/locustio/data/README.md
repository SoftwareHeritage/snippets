# Data for locust.io tests #

This directory contains a small sample of the existing data in Software Heritage.

For each table, the sample was generated using the following command:

``` sql
\copy (select id from person tablesample bernoulli (0.001)) to '/tmp/person' with (format csv, header);
```

The sample was then sorted, and the '\x' escape sequences removed.
