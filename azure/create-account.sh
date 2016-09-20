#!/usr/bin/env bash
# Create 16 storages and 1 container per storage

# pre-requisite:
# npm install azure-cli
# (no debian package for now)


resource_group=swh-resource
container_name="contents"

for name in {0..9} {a..f}; do
    account_name="${name}euwestswh"
    azure storage account create \
          --resource-group $resource_group \
          --kind BlobStorage \
          --location westeurope \
          --access-tier Hot \
          --sku-name LRS \
          $account_name

    account_key=$(azure storage account keys list \
                        --resource-group $resource_group \
                        $account_name | grep 'key1' | awk '{print $3}')

    azure storage container create \
          --account-name $account_name \
          --account-key $account_key \
          --permission Off \
          $container_name

    echo $account_name $account_key $container_name
done
