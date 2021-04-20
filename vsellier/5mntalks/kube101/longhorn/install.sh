#!/bin/bash

helm repo add longhorn https://charts.longhorn.io
helm repo update
helm install -f values.yaml longhorn/longhorn --name longhorn --namespace longhorn-system
