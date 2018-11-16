#!/bin/bash

if [ "$#" != 3 ]; then
    echo "Usage: $0 remote_addr range_start range_end"
    echo "Generate the ranges with:"
    echo
    echo "    s=8; python3 -c \"for i in range(\$s): print('{:05x} {:05x}'.format(0x100000 // \$s * i, 0x100000 // \$s * (i + 1) - 1))\""
    exit 1
fi

ip=$1
range_start=$2
range_end=$3

scp ~/.ssh/id_ed25519.pub "zack@$ip:seirl_key.pub"
scp -r ~/.aws "zack@$ip:aws"

ssh "zack@$ip" <<EOF
sudo mkdir -p /root/.ssh
sudo cp /home/zack/seirl_key.pub /root/.ssh/authorized_keys
sudo cp -r /home/zack/aws /root/.aws
sudo chown -R root:root /root
EOF

ssh -t "root@$ip" <<EOF
set -e

apt install -y python3 python3-venv rsync tmux git libunwind-dev bmon
test -f /etc/ssh/ssh_host_ecdsa_key || dpkg-reconfigure openssh-server

which azcopy || ( wget -O azcopy.tar.gz https://aka.ms/downloadazcopylinux64 \
    && tar -xf azcopy.tar.gz && ./install.sh )

which azcopy >/dev/null

test -e venv || python3 -m venv venv
source venv/bin/activate
pip install wheel
pip install -U awscli

test -e snippets || git clone \
    https://forge.softwareheritage.org/source/snippets.git
cd snippets/
git pull -r

chown -R root:root /root

cd seirl/awsupload/obj
pip install -r requirements.txt

mkdir -p /tmp/content-tmp

echo !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
echo ! Starting tmux with command !
echo !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
tmux new-session -s upload -d "./get_content.py $range_start $range_end"
EOF
