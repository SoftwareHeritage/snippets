#!/usr/bin/env bash

# as a first step, connect to the newly vm created
# $ ssh -i ~/.ssh/id_rsa_inria testadmin@<worker>
# then as root
# $ sudo su -
# first add a generated pass
# $ passwd

# Then permit root connection with ssh
sed -e 's/#PermitRootLogin prohibit-password/PermitRootLogin yes/g' -i /etc/ssh/sshd_config
sed -e 's/PasswordAuthentication no/PasswordAuthentication yes/g' -i /etc/ssh/sshd_config
systemctl restart sshd.service

# disconnect from the current connection
# $ logout
# reconnect as root
# scp the provision-vm.sh script to the root user of the vm
# $ scp provision-vm.sh root@<worker>
# connect to the vm
# $ ssh root@<worker>
# $ chmod +x provision-vm.sh
# trigger the script provision-vm.sh
# $ ./provision-vm.sh
