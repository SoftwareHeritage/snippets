#!/bin/bash

set -ex

cd /

ORIG_HOSTNAME="$(hostname)"
HOSTNAME=${ORIG_HOSTNAME/-*/}.euwest.azure

IP=$(ip a | grep 192 | awk '{print $2}' | awk -F/ '{print $1}')

apt-get update
apt-get -y -o Dpkg::Options::="--force-confdef" -o Dpkg::Options::="--force-confold" dist-upgrade

deluser testadmin || true
rm -rf /home/testadmin

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
apt-get -y -o Dpkg::Options::="--force-confdef" -o Dpkg::Options::="--force-confold" install resolvconf

mkdir -p /srv/storage/space
mkdir -p /srv/softwareheritage/objects

cat >> /etc/fstab << EOF

uffizi:/srv/storage/space /srv/storage/space nfs rw,soft,intr,rsize=8192,wsize=8192,noauto,x-systemd.automount,x-systemd.device-timeout=10 0 0
uffizi:/srv/softwareheritage/objects /srv/softwareheritage/objects nfs rw,soft,intr,rsize=8192,wsize=8192,noauto,x-systemd.automount,x-systemd.device-timeout=10 0 0
EOF
apt-get -y -o Dpkg::Options::="--force-confdef" -o Dpkg::Options::="--force-confold" install nfs-common
mount -a

### puppet from backport

cat >/etc/apt/sources.list.d/backports.list <<EOF
# This file is managed by Puppet. DO NOT EDIT.
# backports
deb http://deb.debian.org/debian/ jessie-backports main
EOF

cat >/etc/apt/preferences.d/puppet.pref <<EOF
# This file is managed by Puppet. DO NOT EDIT.
Explanation: Pin puppet dependencies to backports
Package: facter hiera puppet puppet-common puppetmaster puppetmaster-common puppetmaster-passenger ruby-deep-merge
Pin: release n=jessie-backports
Pin-Priority: 990
EOF

apt-get update

apt-get -y -o Dpkg::Options::="--force-confdef" -o Dpkg::Options::="--force-confold" dist-upgrade
apt-get -y -o Dpkg::Options::="--force-confdef" -o Dpkg::Options::="--force-confold" install augeas-tools
apt-get -y -o Dpkg::Options::="--force-confdef" -o Dpkg::Options::="--force-confold" -t jessie-backports install puppet

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

puppet agent --test || true

reboot
