import yaml
import os
from os import walk

import pynetbox
import json


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

def get_or_create(funct, value, key="name"):
    if key == "name":
        search_result = funct.filter(value['name'])
    else :
        filter = {f"{key}": value[key]}
        search_result = funct.filter(name=None, **filter)
    if len(search_result) == 0:
        return funct.create(value)
    else :
        return search_result[0]

role = {}
role['name'] = 'to be defined'
role['slug'] = 'to-be-defined'
role['vm_role'] = 'true'

role = get_or_create(nb.dcim.device_roles, role)

cluster_type_id = None
cluster_type = {}
cluster_type['name'] = 'Default cluster type'
cluster_type['slug'] = 'default-cluster-type'

cluster_type = get_or_create(nb.virtualization.cluster_types, cluster_type)
cluster_type_id = cluster_type.id

cluster = {}
cluster['name'] = 'Default cluster'
cluster['type'] = cluster_type_id
get_or_create(nb.virtualization.clusters, cluster)

platform = {}
platform['name'] = "buster"
platform['slug'] = "buster"
get_or_create(nb.dcim.platforms, platform)
platform['name'] = "stretch"
platform['slug'] = "stretch"
get_or_create(nb.dcim.platforms, platform)

dell_manufacturer = {}
dell_manufacturer['name'] = "Dell"
dell_manufacturer['slug'] = "dell"
dell_manufacturer = get_or_create(nb.dcim.manufacturers, dell_manufacturer)

supermicro_manufacturer = {}
supermicro_manufacturer['name'] = "SuperMicro"
supermicro_manufacturer['slug'] = "supermicro"
supermicro_manufacturer = get_or_create(nb.dcim.manufacturers, supermicro_manufacturer)

device_type = {}
device_type["display_name"] = 'OptiPlex 7040'
device_type["model"] = device_type["display_name"]
device_type["slug"] = 'optiplex-7040'
device_type['manufacturer'] = dell_manufacturer.id
device_type["U_height"] = 1
get_or_create(nb.dcim.device_types, device_type, "model")

device_type = {}
device_type["display_name"] = 'PowerEdge R920'
device_type["model"] = device_type["display_name"]
device_type["slug"] = 'poweredge-r920'
device_type['manufacturer'] = dell_manufacturer.id
device_type["U_height"] = 1
get_or_create(nb.dcim.device_types, device_type, "model")

device_type = {}
device_type["display_name"] = 'PowerEdge R330'
device_type["model"] = device_type["display_name"]
device_type["slug"] = 'poweredge-r330'
device_type['manufacturer'] = dell_manufacturer.id
device_type["U_height"] = 1
get_or_create(nb.dcim.device_types, device_type, "model")

device_type = {}
device_type["display_name"] = 'PowerEdge R430'
device_type["model"] = device_type["display_name"]
device_type["slug"] = 'poweredge-r430'
device_type['manufacturer'] = dell_manufacturer.id
device_type["U_height"] = 1
get_or_create(nb.dcim.device_types, device_type, "model")

device_type = {}
device_type["display_name"] = 'PowerEdge R540'
device_type["model"] = device_type["display_name"]
device_type["slug"] = 'poweredge-r540'
device_type['manufacturer'] = dell_manufacturer.id
device_type["U_height"] = 1
get_or_create(nb.dcim.device_types, device_type, "model")

device_type = {}
device_type["display_name"] = 'PowerEdge R740xd'
device_type["model"] = device_type["display_name"]
device_type["slug"] = 'poweredge-r740xd'
device_type['manufacturer'] = dell_manufacturer.id
device_type["U_height"] = 1
get_or_create(nb.dcim.device_types, device_type, "model")

device_type = {}
device_type["display_name"] = 'PowerEdge R7425'
device_type["model"] = device_type["display_name"]
device_type["slug"] = 'poweredge-r7425'
device_type['manufacturer'] = dell_manufacturer.id
device_type["U_height"] = 1
get_or_create(nb.dcim.device_types, device_type, "model")

device_type = {}
device_type["display_name"] = 'PowerEdge R815'
device_type["model"] = device_type["display_name"]
device_type["slug"] = 'poweredge-r815'
device_type['manufacturer'] = dell_manufacturer.id
device_type["U_height"] = 1
get_or_create(nb.dcim.device_types, device_type, "model")

device_type = {}
device_type["display_name"] = 'PowerEdge R930'
device_type["model"] = device_type["display_name"]
device_type["slug"] = 'poweredge-r930'
device_type['manufacturer'] = dell_manufacturer.id
device_type["U_height"] = 1
get_or_create(nb.dcim.device_types, device_type, "model")

device_type = {}
device_type["display_name"] = 'PowerEdge R6525'
device_type["model"] = device_type["display_name"]
device_type["slug"] = 'poweredge-r6525'
device_type['manufacturer'] = dell_manufacturer.id
device_type["U_height"] = 1
get_or_create(nb.dcim.device_types, device_type, "model")

device_type = {}
device_type["display_name"] = 'SSG-6028R-E1CR12L'
device_type["model"] = device_type["display_name"]
device_type["slug"] = 'ssg-6028r-e1cr12l'
device_type['manufacturer'] = supermicro_manufacturer.id
device_type["U_height"] = 1
get_or_create(nb.dcim.device_types, device_type, "model")

device_type = {}
device_type["display_name"] = 'SSG-6028R-OSD072P'
device_type["model"] = device_type["display_name"]
device_type["slug"] = 'ssg-6028r-osd072p'
device_type['manufacturer'] = supermicro_manufacturer.id
device_type["U_height"] = 1
get_or_create(nb.dcim.device_types, device_type, "model")

device_type = {}
device_type["display_name"] = 'SYS-6018R-TDTPR'
device_type["model"] = device_type["display_name"]
device_type["slug"] = 'sys-3018r-tdtpr'
device_type['manufacturer'] = supermicro_manufacturer.id
device_type["U_height"] = 1
get_or_create(nb.dcim.device_types, device_type, "model")

device_type = {}
device_type["display_name"] = 'Precision Tower 7810'
device_type["model"] = device_type["display_name"]
device_type["slug"] = 'precision-tower-7810'
device_type['manufacturer'] = dell_manufacturer.id
device_type["U_height"] = 1
get_or_create(nb.dcim.device_types, device_type, "model")

device_type = {}
device_type["display_name"] = "Standard PC (i440FX + PIIX, 1996)"
device_type["model"] = device_type['display_name']
device_type["slug"] = 'standard-pc-i440fx-piix-1996'
device_type['manufacturer'] = dell_manufacturer.id
device_type["U_height"] = 1
get_or_create(nb.dcim.device_types, device_type, "model")

site = {}
site['name'] = 'Inria Paris'
site['slug'] = 'inria_paris'
get_or_create(nb.dcim.sites, site, 'slug')

site = {}
site['name'] = 'Inria SESI Rocquencourt'
site['slug'] = 'sesi_rocquencourt'
get_or_create(nb.dcim.sites, site, 'slug')

site = {}
site['name'] = 'Inria SESI Rocquencourt - Staging'
site['slug'] = 'sesi_rocquencourt_staging'
get_or_create(nb.dcim.sites, site, 'slug')

tag = {}
tag['name'] = 'Production'
tag['slug'] = 'environment-production'
tag['color'] = 'ff0000'
get_or_create(nb.extras.tags, tag, 'slug')

tag = {}
tag['name'] = 'Staging'
tag['slug'] = 'environment-staging'
tag['color'] = '0000ff'
get_or_create(nb.extras.tags, tag, 'slug')

tag = {}
tag['name'] = 'Imported from puppet facts'
tag['slug'] = 'puppet-import'
tag['color'] = 'bbbbbb'
get_or_create(nb.extras.tags, tag, 'slug')

vlan = {}
vlan['vid'] = '1300'
vlan['name'] = 'Public'
public_vlan = get_or_create(nb.ipam.vlans, vlan, 'vid')
vlan = {}
vlan['vid'] = '440'
vlan['name'] = 'Production'
production_vlan = get_or_create(nb.ipam.vlans, vlan, 'vid')
vlan = {}
vlan['vid'] = '443'
vlan['name'] = 'Staging'
staging_vlan = get_or_create(nb.ipam.vlans, vlan, 'vid')
vlan = {}
vlan['vid'] = '444'
vlan['name'] = 'Administration'
admin_vlan = get_or_create(nb.ipam.vlans, vlan, 'vid')

prefix = {}
prefix['prefix'] = '128.93.193.0/24'
prefix['vlan'] = public_vlan.id
prefix['description'] = 'Public ip range'
get_or_create(nb.ipam.prefixes, prefix, 'prefix')
prefix = {}
prefix['prefix'] = '192.168.100.0/24'
prefix['vlan'] = production_vlan.id
prefix['description'] = 'Internal production ip range'
get_or_create(nb.ipam.prefixes, prefix, 'prefix')
prefix = {}
prefix['prefix'] = '192.168.200.0/24'
prefix['description'] = 'Azure production ip range'
get_or_create(nb.ipam.prefixes, prefix, 'prefix')
prefix = {}
prefix['prefix'] = '192.168.101.0/24'
prefix['description'] = 'OpenVPN ip range'
get_or_create(nb.ipam.prefixes, prefix, 'prefix')
prefix = {}
prefix['prefix'] = '192.168.128.0/24'
prefix['description'] = 'Internal staging ip range'
prefix['vlan'] = staging_vlan.id
get_or_create(nb.ipam.prefixes, prefix, 'prefix')
