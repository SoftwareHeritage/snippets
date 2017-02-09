#!/bin/sh

set -e

cat >> /home/injection/.ssh/authorized_keys <<EOF
ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQC9VE8ET+Iow9GzGnQc8Gup2LI5AvOb5aO29ZF28bVgnPyrOPOYWxVTArt1r5rWNXqboqN5PSJ35XtLQPl5amAbFnLlk3eUxsO71HdeM4ZVPNyotQVqXMQNMnnNzyjH8SVPWjYT8Ehf0tcuuY4PDMapqpw6FAxalon5/LK+nL889Ol5990GcXZFbNljJAWFVLQYkzZhfxe5RL94yn4vZi5g+emd1hfOETWKpSCgtftFEvT0v1sqpMOBrj67uC0mL3S0C6YblZSU5thZaiOvxgAcCHwKcPrXnKKyvhCsMciAbhOPGV/n+7O692aXTLzFtOZqXROEhivGX2Z7ldBuiySx olasd@uffizi
EOF

cat > /etc/apt/sources.list.d/softwareheritage.list <<EOF
deb [trusted=yes] http://debian.internal.softwareheritage.org/ jessie main
EOF

cat > /etc/apt/preferences.d/objstorage_cloud.pref <<EOF
Explanation: Pin python3-azure-storage dependencies to backports
Package: python3-cffi python3-cryptography python3-pkg-resources python3-pyasn1 python3-setuptools
Pin: release n=jessie-backports
Pin-Priority: 990
EOF

apt-get update
apt-get -y dist-upgrade
apt-get -y install mdadm rabbitmq-server python3-swh.objstorage.cloud python3-swh.storage.archiver python3-swh.scheduler

exit 0

for disk in /dev/sd[c-m]; do
    sfdisk $disk <<EOF
unit: sectors

/dev/sdc1 : start=     2048, size=2145384448, Id=fd
/dev/sdc2 : start=        0, size=        0, Id= 0
/dev/sdc3 : start=        0, size=        0, Id= 0
/dev/sdc4 : start=        0, size=        0, Id= 0
EOF
done;
mdadm --create /dev/md0 --level 0 --raid-devices 11 /dev/sd[c-m]1
/usr/share/mdadm/mkconf > /etc/mdadm/mdadm.conf
update-initramfs -k all -u
