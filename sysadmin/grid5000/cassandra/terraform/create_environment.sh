#!/bin/bash

echo "*********** Preparing environment"
# TODO install terraform if not present

python3 -m venv ~/.venv
source ~/.venv/bin/activate
pip install ansible

echo "*********** Reserve and initialize nodes"
terraform apply

# TODO status check

echo "*********** Terraform output"
terraform output --json | jq '' | tee > environment.json
