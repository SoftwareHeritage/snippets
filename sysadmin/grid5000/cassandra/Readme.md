Grid5000 terraform provisioning
===============================

- [Grid5000 terraform provisioning](#grid5000-terraform-provisioning)
  - [Prerequisite](#prerequisite)
  - [Run](#run)
    - [Local (on vagrant)](#local-on-vagrant)
    - [On Grid5000](#on-grid5000)
      - [Via the custom script](#via-the-custom-script)
        - [Reservation configuration](#reservation-configuration)
        - [Nodes configuration](#nodes-configuration)
        - [Execution](#execution)
      - [(deprecated) With terraform](#deprecated-with-terraform)
  - [Cleanup](#cleanup)
  - [TODO](#todo)
  - [Possible improvments](#possible-improvments)

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

Useful link:
Hardware information: https://www.grid5000.fr/w/Hardware
Resources availability: https://www.grid5000.fr/w/Status

#### Via the custom script

##### Reservation configuration

The configuration is defined on the `environment.cfg` file.
In this file, g5k sites, cluster, nodes and reparition can be configured.

##### Nodes configuration

The node installation is done by ansible. It needs to know the node topology to correctly configure the tools (zfs pools and dataset, cassandra seed, ...)

The configuration is centralized in the `ansible/hosts.yml` file

##### Execution

1. Transfer the files on g5k on the right site:

```
rsync -avP --exclude .vagrant --exclude .terraform cassandra access.grid5000.fr:/<site name>
```

2. Connect to the right site

```
ssh access.grid5000.fr
ssh <site>
```

3. Reserve the disks

The disks must be reserved before the node creation or they will not be detected on the nodes

```
./00-reserve_disks.sh
```

check the status of the job / the resources status to be sure they are correctly reserved

```
$ oarstat -fj <OAR JOB ID> | grep state
    state = Running
```
The state must be running

4. Launch a complete run

```
./01-run.sh
```

DISCLAIMER: Actually, it only runs the following steps:
- reserve the nodes
- install the os on all the nodes
- launch ansible on all the nodes

The underlying scripts can by run indepedently if they need to be restarted:
- `02-reserver-nodes.sh`: Reserve the node resources
- `03-deploy-nodes.sh`: Install the os (only one time per reservation) and launch ansible on all the nodes. To force an os resinstalltion, remove the `<JOB_ID_>.os.stamp` file

5. Cleanup the resources

To release the nodes:

```
oarstat -u
<job id>
<job id>
```

```
oardel <jobid>
```
#### (deprecated) With terraform

Terraform can be greate to reserve the resources but it doesn't not allow manage the scheduled jobs

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

[X] variablization of the script
[X] Ansible provisionning of the nodes
[X] disk initialization
[X] support different cluster topologies (nodes / disks / ...)
[X] cassandra installation
[X] swh-storage installation
[ ] journal client for mirroring
[ ] monitoring by prometheus
[ ] Add a tool to erase the reserved disks (useful to avoid zfs to detect the previous pools and be able to restart from scratch)

## Possible improvments

[ ] Use several besteffort jobs for cassandra nodes. They can be interrupted but don't have duration restrictions.
