FROM prom/prometheus

ARG FEDERATED_PROMETHEUS_IP

COPY conf/prometheus.yml /etc/prometheus/prometheus.yml

RUN sed -i "s/@@FEDERATED_PROMETHEUS_IP@@/${FEDERATED_PROMETHEUS_IP}/g" /etc/prometheus/prometheus.yml
