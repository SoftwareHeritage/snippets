# Fact importer into netbox

Samall utility to import the puppet facts content into netbox

## usage


### first time

```
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
```

### Import facts

```
. .venv/bin/activate
export NETBOX_URL=http://localhost:8080
export NETBOX_TOKEN=<api token>
export FACTS_DIRECTORY=/path/to/puppet-environment/octocatalog-diff/facts">
python run.py
```
