#!/bin/bash

set -ex

cd /

ORIG_HOSTNAME="$(hostname)"
HOSTNAME=${ORIG_HOSTNAME/-*/}.euwest.azure

IP=$(ip a | grep 192 | awk '{print $2}' | awk -F/ '{print $1}')

apt-get update
apt-get -y -o Dpkg::Options::="--force-confdef" -o Dpkg::Options::="--force-confold" dist-upgrade

echo $HOSTNAME > /etc/hostname
hostnamectl set-hostname $HOSTNAME
cat >> /etc/hosts << EOF
$IP $HOSTNAME.internal.softwareheritage.org $HOSTNAME

192.168.100.100 db
192.168.100.101 uffizi
192.168.100.31 moma
EOF

mkdir -p /etc/resolvconf/resolv.conf.d
echo search internal.softwareheritage.org > /etc/resolvconf/resolv.conf.d/tail
apt-get -y -o Dpkg::Options::="--force-confdef" -o Dpkg::Options::="--force-confold" install resolvconf nfs-common

apt-get update

apt-get -y -o Dpkg::Options::="--force-confdef" -o Dpkg::Options::="--force-confold" dist-upgrade
apt-get -y -o Dpkg::Options::="--force-confdef" -o Dpkg::Options::="--force-confold" install augeas-tools puppet


# FIXME: Is this useful?
augtool << "EOF"
set /files/etc/puppet/puppet.conf/main/pluginsync true
set /files/etc/puppet/puppet.conf/main/server pergamon.internal.softwareheritage.org
save
EOF

mkdir -p /etc/facter/facts.d
echo location=azure_euwest > /etc/facter/facts.d/location.txt

service puppet stop
systemctl disable puppet.service
puppet agent --enable

augtool << "EOF"
set /files/etc/puppet/puppet.conf/agent/server pergamon.internal.softwareheritage.org
set /files/etc/puppet/puppet.conf/agent/report true
set /files/etc/puppet/puppet.conf/agent/pluginsync true
save
EOF

rm -rf /root/.ssh

deluser testadmin
rm -rf /home/testadmin

puppet agent --test || true

reboot
