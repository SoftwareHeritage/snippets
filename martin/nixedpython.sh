#!/bin/bash

# this file can be shabanged in Python scripts that should run below a Nix env

source /applis/site/nix.sh
cd $(dirname $(realpath $1))
python -u $*
