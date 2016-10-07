#!/bin/sh

worker=worker01

zone=westeurope
resource_prefix=euwest
resource_group="${resource_prefix}-workers"

image=credativ:Debian:8:latest

# "default" subnet in the "swh-vnet" virtual network of the "swh-resource" resource group
subnet=/subscriptions/49b7f681-8efc-4689-8524-870fc0c1db09/resourceGroups/swh-resource/providers/Microsoft.Network/virtualNetworks/swh-vnet/subnets/default

# Change for virtual machine size. Standard_DS = SSD; Standard_S = Standard disk
size=Standard_DS11_v2
# size=Standard_D11_v2

# SSD
disk_group="${resource_prefix}workersdisks"
# Standard
# disk_group="${resource_prefix}stddisks"

diagnostics_resource=swhresourcediag966



azure vm create \
      -g "${resource_group}" \
      -n "${worker}-${resource_prefix}" \
      -l "${zone}" \
      -y Linux -Q "${image}" \
      -S "${subnet}" -f "${worker}-${resource_prefix}-if" \
      -u testadmin -M ~/.ssh/id_rsa.inria.pub \
      -o "${disk_group}" \
      -z "${size}" \
      --boot-diagnostics-storage-uri "http://${diagnostics_resource}.blob.core.windows.net/"
