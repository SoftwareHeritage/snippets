Grid5000 terraform provisioning
===============================

Prerequisite
------------

Tools
#####

terraform >= 13.0
vagrant >= 2.2.3 [for local tests only]

Credentials
###########

* grid5000 credentials
```
cat <<EOF > ~/.grid5000.yml
uri: https://api.grid5000.fr
username: username
password: password
EOF
```
Theses credentials will be used to interact with the grid5000 api to create the jobs

* Private/public key files (id_rsa) in the `~/.ssh` directory
  
The public key will be installed on the nodes

Run
---

### Local (on vagrant)

The `Vagrantfile` is configured to provision 3 nodes, install cassandra and the configure the cluster using the ansible configuration:

```
vagrant up
vagrant ssh cassandra1
sudo -i
nodetool status
```

If everything is ok, the `nodetool` command line returns:
```
root@cassandra1:~# nodetool status
Datacenter: datacenter1
=======================
Status=Up/Down
|/ State=Normal/Leaving/Joining/Moving
--  Address        Load       Tokens  Owns (effective)  Host ID                               Rack 
UN  10.168.180.12  15.78 KiB  256     67.9%             05d61a24-832a-4936-b0a5-39926f800d09  rack1
UN  10.168.180.11  73.28 KiB  256     67.0%             23d855cc-37d6-43a7-886e-9446e7774f8d  rack1
UN  10.168.180.13  15.78 KiB  256     65.0%             c6bc1eff-fa0d-4b67-bc53-fc31c6ced5bb  rack1
```

Cassandra can take some time to start, so you have to wait before the cluster stabilize itself.

### On Grid5000

* Initialize terraform modules (first time only)
```
terraform init
```

* Test the plan

It only check the status of the declared resources compared to the grid5000 status. 
It's a read only operation, no actions on grid5000 will be perform.

```
terraform plan
```

* Execute the plan

```
terraform apply
```

This action creates the job, provisions the nodes according the `main.tf` file content and install the specified linux distribution on it.

This command will log the reserved node name in output.
For example for a 1 node reservation:

```
grid5000_job.cassandra: Creating...
grid5000_job.cassandra: Still creating... [10s elapsed]
grid5000_job.cassandra: Creation complete after 11s [id=1814813]
grid5000_deployment.my_deployment: Creating...
grid5000_deployment.my_deployment: Still creating... [10s elapsed]
grid5000_deployment.my_deployment: Still creating... [20s elapsed]
grid5000_deployment.my_deployment: Still creating... [30s elapsed]
grid5000_deployment.my_deployment: Still creating... [40s elapsed]
grid5000_deployment.my_deployment: Still creating... [50s elapsed]
grid5000_deployment.my_deployment: Still creating... [1m0s elapsed]
grid5000_deployment.my_deployment: Still creating... [1m10s elapsed]
grid5000_deployment.my_deployment: Still creating... [1m20s elapsed]
grid5000_deployment.my_deployment: Still creating... [1m30s elapsed]
grid5000_deployment.my_deployment: Still creating... [1m40s elapsed]
grid5000_deployment.my_deployment: Still creating... [1m50s elapsed]
grid5000_deployment.my_deployment: Still creating... [2m0s elapsed]
grid5000_deployment.my_deployment: Still creating... [2m10s elapsed]
grid5000_deployment.my_deployment: Creation complete after 2m12s [id=D-0bb76036-1512-429f-be99-620afa328b26]

Apply complete! Resources: 2 added, 0 changed, 0 destroyed.

Outputs:

nodes = [
  "chifflet-6.lille.grid5000.fr",
]
```
It's now possible to connect to the nodes:
```
$ ssh -A access.grid5000.fr
$ ssh -A root@chifflet-6.lille.grid5000.fr
Linux chifflet-6.lille.grid5000.fr 4.19.0-16-amd64 #1 SMP Debian 4.19.181-1 (2021-03-19) x86_64
Debian10-x64-base-2021060212
 (Image based on Debian Buster for AMD64/EM64T)
  Maintained by support-staff <support-staff@lists.grid5000.fr>

Doc: https://www.grid5000.fr/w/Getting_Started#Deploying_nodes_with_Kadeploy

root@chifflet-6:~#
```

Cleanup
-------

To destroy the resources before the end of the job:

```
terraform destroy
```

If the job is stopped, simply remove the `terraform.tfstate` file:
```
rm terraform.tfstate
```

## TODO

[ ] variablization of the script
[ ] Ansible provisionning of the nodes
[ ] disk initialization
[ ] support different cluster topologies (nodes / disks / ...)
[ ] cassandra installation
[ ] swh-storage installation
[ ] ...
