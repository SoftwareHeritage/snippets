- Install ansible and the netbox module
```
# sudo apt install ansible python3-pynetbox
# ansible-galaxy collection install netbox.netbox
```

- Generate a new api token for your user in netbox
  https://inventory.internal.admin.swh.network/user/api-tokens/

- Store the token in a yaml file, for example in `~/.ansible/netbox.yaml`

```
cat <EOF >~/.ansible/netbox.yaml
netbox_url: https://inventory.internal.admin.swh.network
netbox_token: abcdef
EOF
```

- Execute ansible:
```
ansible-playbook --extra-vars @~/.ansible/netbox.yaml  playbook.yaml -i inventory
```
