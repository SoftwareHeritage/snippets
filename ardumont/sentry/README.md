sentry
=======

Basic cli to analyze sentry data in [1].

# Requisites

You need a sentry account in [1]
You need to generate an api auth token in [2]

[1] https://sentry.softwareheritage.org

[2] https://sentry.softwareheritage.org/settings/account/api/auth-tokens/


# Virtualenv

Enter the virtualenv (this is using pipenv):
```
pipenv shell
```

# Use case samples

## List projects

```
python -m sentry --token $TOKEN project \
  | jq .
{
  "swh-objstorage": {
    "id": "4",
    "name": "swh-objstorage"
  },
  "swh-storage": {
    "id": "3",
    "name": "swh.storage"
  },
  ...
}
```

## List issues

```
$ python -m sentry --token $TOKEN \
    issue --project-slug swh-storage \
    | jq .
[{
  ...
  "1438": {
    "short-id": "SWH-STORAGE-AP",
    "status": "unresolved",
    "metadata": {
      "function": "_content_add_metadata",
      "type": "HashCollision",
      "value": "('sha1', b'\\xc6\\xfd\\t\\xe3t\\xb5/\\x9c\\xf7\\x96\\xb7D\\xf1\\xe7\\xcc\\x0b)\\x94JS', [{'sha1_git': b'\\xbc\\x90If\\x02\\x01\\xcc\\x94B;\\xc3\\xc5,\\xbf,\\x97\\xc16\\x920', 'blake2s256': b'\\x8fe5]\\x97\\xad\\xe2\\x05:B\\x8bJ\\x8f?i\\xa2|S>\\x7f.\\xad\\x18\\xe9\\x04\\xba\\x17\\xeb\\xa6\\x97\\x87\\x03', 'sha256': b'`\\x194\\xa7\\x08-\\x1c_\\xa8c\\x99\\xdb3~\\xda6\\xf5\\x13g~:#\\xd3\\xfeP\\xcfT!\\xa05\\xdar', 'sha1': b'\\xc6\\xfd\\t\\xe3t\\xb5/\\x9c\\xf7\\x96\\xb7D\\xf1\\xe7\\xcc\\x0b)\\x94JS'}])",
      "filename": "swh/storage/storage.py"
    }
  },
  ...
]
```

## Detailed issue

```
$ python -m sentry --token $TOKEN issue --issue-id 1438 | jq .
{
  "short-id": "SWH-STORAGE-AP",
  "title": "HashCollision: ('sha1', b'\\xf9y\\xcb\\xe0\\xb8\\xe7\\xc7-\\x94\\xfe\\x96\\x98\\x8dS\\xce,\\x8cb{w', [{'sha1_git': b'\\xfe\\xd2...",
  "first-seen": "2020-03-18T16:25:46.502583Z",
  "last-seen": "2020-03-19T13:34:25Z",
  "count": "252",
  "status": "unresolved",
  "project": "swh-storage",
  "culprit": "content_add",
  "metadata": {
    "function": "_content_add_metadata",
    "type": "HashCollision",
    "value": "('sha1', b'\\xf9y\\xcb\\xe0\\xb8\\xe7\\xc7-\\x94\\xfe\\x96\\x98\\x8dS\\xce,\\x8cb{w', [{'sha1_git': b'\\xfe\\xd2\\xf4m\\x8cZ\\xcf\\x16q\\xefDv\\xdf\\xf3\\xd6\\xad\\x1bPn%', 'blake2s256': b'}\\x84\\xe5\\xbf\\x14\\xcc\\xce\\x17\\x83\\xb9\\xf0\\xa0\\x9d\\x89\\xb2\\x97\\xbcS\\xd7\\xa2\\xdc\\xb3\\xd5r\\xaewB\\x88\\xcb\\\\\\xcd9', 'sha256': b'\\xc9\\x0b\\xca@e\\x0e\\x17\\x9f\\xc8\\x15{0\\xc8~\\xeb\\xc8\\x1alB\\x88\"W\\x03\\xc6\\x15J\\xa7\\x89~ll\\xf1', 'sha1': b'\\xf9y\\xcb\\xe0\\xb8\\xe7\\xc7-\\x94\\xfe\\x96\\x98\\x8dS\\xce,\\x8cb{w'}])",
    "filename": "swh/storage/storage.py"
  }
}
```

## Events per issue

```
python -m sentry --token $TOKEN events --issue-id 1438 | jq .
{
  "a253b8d5200042768d779db1f3761838": {
    "culprit": "content_add",
    "title": "HashCollision: ('sha1', b'\\xc2f\\x92b\\x1b|\\x9dn\\x14!G\\xc5|\\xf5\\xcf\\x0f\\x145\\x92\\x8c', [{'sha1_git': b'@\\xfa\\x9a\\x...",
    "message": "('sha1', b'\\xc2f\\x92b\\x1b|\\x9dn\\x14!G\\xc5|\\xf5\\xcf\\x0f\\x145\\x92\\x8c', [{'sha1_git': b'@\\xfa\\x9a\\x04I!&X\\xcfx\\xfeZT\\xdd#\\xf2\\xaf\\xbe2{', 'blake2s256': b'\\xf5\\xf1z\\r6\\xdd5+\\xa4\\x11I\\x8cTI\\xd1\\xe7|\\x18y\\xf2\\xfa\\x9e]\\xdbF\\x0c;\\xf2\\xc8\\xa8[K', 'sha256': b'+\\x02]\\xadf\\xda\\x17\\xe66\\xcbS\\x03O\\x83\\x9d\\x17\\xb2\\xce\\xeb\\x12\\x8e\\x98\\x0e\\xe1>K\\x99\\x88\\xa2w\\xff\\x16', 'sha1': b'\\xc2f\\x92b\\x1b|\\x9dn\\x14!G\\xc5|\\xf5\\xcf\\x0f\\x145\\x92\\x8c'}])",
    "project-id": "3",
    "group-id": "1438"
  },
  "fab52b7c4d85492193196baadf3de7cc": {
    "culprit": "content_add",
    "title": "HashCollision: ('sha1', b'\\xf9y\\xcb\\xe0\\xb8\\xe7\\xc7-\\x94\\xfe\\x96\\x98\\x8dS\\xce,\\x8cb{w', [{'sha1_git': b'\\xfe\\xd2...",
    "message": "('sha1', b'\\xf9y\\xcb\\xe0\\xb8\\xe7\\xc7-\\x94\\xfe\\x96\\x98\\x8dS\\xce,\\x8cb{w', [{'sha1_git': b'\\xfe\\xd2\\xf4m\\x8cZ\\xcf\\x16q\\xefDv\\xdf\\xf3\\xd6\\xad\\x1bPn%', 'blake2s256': b'}\\x84\\xe5\\xbf\\x14\\xcc\\xce\\x17\\x83\\xb9\\xf0\\xa0\\x9d\\x89\\xb2\\x97\\xbcS\\xd7\\xa2\\xdc\\xb3\\xd5r\\xaewB\\x88\\xcb\\\\\\xcd9', 'sha256': b'\\xc9\\x0b\\xca@e\\x0e\\x17\\x9f\\xc8\\x15{0\\xc8~\\xeb\\xc8\\x1alB\\x88\"W\\x03\\xc6\\x15J\\xa7\\x89~ll\\xf1', 'sha1': b'\\xf9y\\xcb\\xe0\\xb8\\xe7\\xc7-\\x94\\xfe\\x96\\x98\\x8dS\\xce,\\x8cb{w'}])",
    "project-id": "3",
    "group-id": "1438"
  },
  ...
}
```
