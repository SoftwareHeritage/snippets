# Fact importer into netbox

Samall utility to import the puppet facts content into netbox

## usage


### first time

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
```

### Initialize netbox

the ``init.py`` script initialize the following netbox properties in order to import the puppet facts :
- device providers
- device types
- vlan
- ip prefixes
- tags
- platforms
- device roles

To run it :

```bash
. .venv/bin/activate
export NETBOX_URL=http://localhost:8080
export NETBOX_TOKEN=<api token>
export FACTS_DIRECTORY=/path/to/puppet-environment/octocatalog-diff/facts">
python run.py
```


### Import facts

```bash
. .venv/bin/activate
export NETBOX_URL=http://localhost:8080
export NETBOX_TOKEN=<api token>
export FACTS_DIRECTORY=/path/to/puppet-environment/octocatalog-diff/facts">
python run.py
```
