#!/bin/bash

cd ~/swh-environment
.venv/bin/pip install \
    -e ./swh-core \
    -e ./swh-model \
    -e ./swh-objstorage \
    -e ./swh-scheduler \
    -e ./swh-storage \
    -e ./swh-vault \
    -e ./swh-indexer \
    -e ./swh-web \
    -e ./swh-lister
