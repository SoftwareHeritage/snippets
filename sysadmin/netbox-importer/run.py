import yaml
import os
from os import walk

import pynetbox
import json

output_directory="./output"
default_device_role = 'to be defined'
default_device_role_id = None
default_cluster = 'Default cluster'
default_cluster_id = None


class Facts(yaml.YAMLObject):
    yaml_tag = u"!ruby/object:Puppet::Node::Facts"

    def init(self, loader, name, values, timestamp, expiration):
        self.name = name
        self.values = values
        self.expiration = expiration
        self.timestamp = timestamp


# yaml.add_multi_constructor(u"!ruby/object:Puppet::Node::Facts", construct_ruby_object)
# yaml.add_constructor(u"!ruby/sym.*", construct_ruby_sym)
def check_end_get_object_id(result, name, filter):
    count = len(result)
    if count == 0:
        print(f"{name} {filter} not found")
        exit(1)
    elif count > 1:
        print(f"More than 1 {name} exist for name {filter}")
        exit(1)

    return result[0]['id']

def get_device_role_id(name):
    device_roles = nb.dcim.device_roles.filter(name=name)
    return check_end_get_object_id(device_roles, "device role", name)

def get_device_type_id(model):
    device_types = nb.dcim.device_types.filter(model=model)
    return check_end_get_object_id(device_types, "device type", model)

def get_platform_id(name):
    platforms = nb.dcim.platforms.filter(name=name)
    return check_end_get_object_id(platforms, "platform", name)

def get_site_id(name):
    sites = nb.dcim.sites.filter(name=name)
    return check_end_get_object_id(sites, "sites", name)

def get_cluster_id(name):
    clusters = nb.virtualization.clusters.filter(name=name)
    return check_end_get_object_id(clusters, "cluster", name)

def get_device(name):
    device = nb.dcim.devices.filter(name)
    count = len(device)
    if count == 0:
        return None
    elif count == 1:
        return device[0]
    else:
        print("More than one device found for name={name}")
        exit(1)

def get_virtual_machine(name):
    vms = nb.virtualization.virtual_machines.filter(name)
    count = len(vms)
    if count == 0:
        return None
    elif count == 1:
        return vms[0]
    else:
        print("More than one device found for name={name}")
        exit(1)

def get_or_create_ip_address(address):
    ip = nb.ipam.ip_addresses.filter(address=address)

    count = len(ip)

    if count == 0:
        print(f"  Creating ip {address}")
        ip = {}
        ip['address'] = address

        ip = nb.ipam.ip_addresses.create(ip)
        return ip['id']
    elif count == 1:
        return ip[0]['id']
    else:
        print(f"There are more then one ip addresse defined for {address}")
        exit(1)

def create_or_update_device(facts):
    device_type = facts.values['dmi']['product']['name']
    device_type_id = get_device_type_id(device_type)
    print("device_type_id: ", device_type_id)
    platform = facts.values['lsbdistcodename']
    platform_id = get_platform_id(platform)
    print(f"platform_id: {platform_id}")
    site_id = get_site_id(facts.values['location'])

    device = get_device(facts.name)

    if device == None :
        device = {}

        device['device_role'] = default_device_role_id
        device['name'] = facts.name
        device['manufacturer'] = facts.values['manufacturer']
        device['device_type'] = device_type_id
        device['platform'] = platform_id
        device['serial'] = facts.values['boardserialnumber'] if 'boardserialnumber' in facts.values else ''
        device['status'] = 'active'
        device['site'] = site_id

        print(f"  Creating {device['name']} via api")
        print(json.dumps(device))

        nb.dcim.devices.create(device)

    else:
        print(f"Device {facts.name} already exists")

def create_or_update_virtual_machine(facts):
    print(vars(facts))

    vm = get_virtual_machine(facts.name)

    if vm == None :
        print(f"VM {facts.name} needs to be created")

        vm = {}
        vm['name'] = facts.name
        vm['cluster'] = default_cluster_id
        vm['role'] = default_device_role_id
        vm['platform'] = get_platform_id(facts.values['lsbdistcodename'])
        vm['memory'] = "%.0f" % facts.values['memorysize_mb']
        vm['vcpus'] = facts.values['physicalprocessorcount']

        # TODO create all ips + properties
        # TODO Create interfaces
        # TODO associate interfaces and ips
        # TODO mutualize with devices
        ip_id = get_or_create_ip_address(facts.values['networking']['ip'])
        #vm['primaryip'] = facts.values['networking']['ip']

        print(f"  Creating {vm['name']} via api")
        print(json.dumps(vm))
        nb.virtualization.virtual_machines.create(vm)

    else:
        print(f"VM {facts.name} already exists")
    exit(1)

#####################################
## Start

env_url='NETBOX_URL'
env_token='NETBOX_TOKEN'
env_facts_directory='FACTS_DIRECTORY'

if env_url not in os.environ or env_token not in os.environ or env_facts_directory not in os.environ:
    print(f"{env_url}, {env_token} and {env_facts_directory} must be declared in the environement")
    exit(1)

netbox_url = os.environ[env_url]
netbox_token = os.environ[env_token]
facts_directory = os.environ[env_facts_directory]

nb = pynetbox.api(netbox_url, token=netbox_token)

default_device_role_id = get_device_role_id(default_device_role)
# print("The default device role id for '{}' is : {}".format(default_device_role, default_device_role_id))
default_cluster_id = get_cluster_id(default_cluster)

for (_, _, filenames) in walk(facts_directory) :
    for filename in filenames:
        print("filename : " , filename)
        full_filename = facts_directory + "/" + filename
        with open(r"{}".format(full_filename)) as file:

            facts = yaml.load(file, Loader=yaml.FullLoader)

            print("\tName : ", facts.name)
            print("\tis_virtual :", facts.values['is_virtual'])

            if facts.values['is_virtual'] == False:
                create_or_update_device(facts)
            elif facts.values['is_virtual'] == True :
                create_or_update_virtual_machine(facts)
            else:
                print("Virtual status can't be found for facts :")
                print(facts)
