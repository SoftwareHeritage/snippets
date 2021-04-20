#!/bin/bash

for version in {0..2}; do
    docker build --build-arg VERSION="v${version}" -t "registry.demo/demo:v${version}" .
    docker push "registry.demo/demo:v${version}"
done
