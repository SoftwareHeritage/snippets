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


apt-get -y -o Dpkg::Options::="--force-confdef" -o Dpkg::Options::="--force-confold" install puppet
service puppet stop
systemctl disable puppet.service
puppet agent --enable

cat > /etc/puppet/puppet.conf << EOF
[agent]
server=pergamon.internal.softwareheritage.org
report            = true
pluginsync        = true
EOF

rm -r /root/.ssh

puppet agent -t

reboot
