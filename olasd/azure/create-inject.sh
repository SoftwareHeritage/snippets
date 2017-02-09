#!/bin/sh

set -e

group="injection"
storage_account="${group}"

location="westeurope"

vm_name="$1"

vm_size="Standard_DS5_v2"
vm_subnet="/subscriptions/49b7f681-8efc-4689-8524-870fc0c1db09/resourceGroups/swh-resource/providers/Microsoft.Network/virtualNetworks/swh-vnet/subnets/default"
vm_diagnostics="http://swhresourcediag966.blob.core.windows.net/"

vm_user="injection"
vm_sshkey="~/.ssh/id_rsa.inria.pub"

vm_ndisks=11

if ! azure group show "$group" >/dev/null; then
    azure group create "$group" "$location"
fi

if ! azure storage account show -g "$group" "$storage_account"; then
    azure storage account create -g "$group" -l "$location" "$storage_account"
fi

azure vm create \
      -g "${group}" \
      -n "${vm_name}" \
      -l "${location}" \
      -y Linux -Q credativ:Debian:8:latest \
      -S "${vm_subnet}" \
      -f "${vm_name}-if" \
      -i "${vm_name}-public" --public-ip-domain-name "swh${vm_name}" --public-ip-idletimeout 30 \
      -u "${vm_user}" -M "${vm_sshkey}" \
      -o "${storage_account}" \
      -z "${vm_size}" \
      --boot-diagnostics-storage-uri "${vm_diagnostics}"

for disk in $(seq 1 "${vm_ndisks}"); do
    azure vm disk attach-new \
          -g "${group}" \
          -n "${vm_name}" \
          -z 1023 \
          -d "${vm_name}-data${disk}.vhd" \
          -l "${disk}" \
          -o "${storage_account}"
done

vm_hostname="swh${vm_name}.${location}.cloudapp.azure.com"
scp -i "${vm_sshkey}" provision-inject.sh "${vm_user}@${vm_hostname}:"
ssh -i "${vm_sshkey}" "${vm_user}@${vm_hostname}" sudo bash provision-inject.sh
