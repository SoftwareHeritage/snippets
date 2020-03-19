sentry
=======

Enter the virtualenv (this is using pipenv):
```
pipenv shell
```

Limited use case so far:

List existing projects in our sentry instance:

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

List issues:
```
$ python -m sentry --token $TOKEN \
    issue --project-slug swh-storage \
    | jq ".[0].metadata"
{
  "function": "_content_add_metadata",
  "type": "HashCollision",
  "value": "('sha1', b'\\xc6\\xfd\\t\\xe3t\\xb5/\\x9c\\xf7\\x96\\xb7D\\xf1\\xe7\\xcc\\x0b)\\x94JS', [{'sha1_git': b'\\xbc\\x90If\\x02\\x01\\xcc\\x94B;\\xc3\\xc5,\\xbf,\\x97\\xc16\\x920', 'blake2s256': b'\\x8fe5]\\x97\\xad\\xe2\\x05:B\\x8bJ\\x8f?i\\xa2|S>\\x7f.\\xad\\x18\\xe9\\x04\\xba\\x17\\xeb\\xa6\\x97\\x87\\x03', 'sha256': b'`\\x194\\xa7\\x08-\\x1c_\\xa8c\\x99\\xdb3~\\xda6\\xf5\\x13g~:#\\xd3\\xfeP\\xcfT!\\xa05\\xdar', 'sha1': b'\\xc6\\xfd\\t\\xe3t\\xb5/\\x9c\\xf7\\x96\\xb7D\\xf1\\xe7\\xcc\\x0b)\\x94JS'}])",
  "filename": "swh/storage/storage.py"
}
```

Note:
You need a sentry account in [1]
You need to generate an api auth token in [2]

[1] https://sentry.softwareheritage.org

[2] https://sentry.softwareheritage.org/settings/account/api/auth-tokens/
