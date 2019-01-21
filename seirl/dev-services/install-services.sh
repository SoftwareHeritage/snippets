#!/bin/bash

cd "$( dirname $0 )"

services_dir="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
mkdir -p "$services_dir"
cp *.service *.target "$services_dir"

systemctl --user daemon-reload
