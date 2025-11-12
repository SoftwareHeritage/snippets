# Installation

- Create or use a venv
- Install `python-gitlab`

- Configure `python-gitlab`
  - Create an access token with permissions `admin_mode, api`
  - Create a file `$HOME/.python-gitlab.cfg` with the content
```
[swh-admin]
url = https://gitlab.softwareheritage.org
api_version = 4
private_token = <your token>
```

# Test the configuration

- Adapt the `configuration.yml` file
- Test it
```
python3 cli.py -g swh-admin  [groups|projects] configuration.yml
```
- If the changes are ok, apply with
- ```
python3 cli.py -g swh-admin --do-it  [groups|projects] configuration.yml
```
