import csv
import os
import os.path
import subprocess

from swh.model.hashutil import hash_to_bytes
from swh.objstorage.api.client import RemoteObjStorage
from swh.objstorage.exc import ObjNotFoundError

BASE_DIR = os.path.expanduser('~/datasets/')

GEMSPEC_LIST_QUERY = """
select encode(name, 'escape'), encode(sha1, 'hex')
from directory_entry_file
inner join content on (sha1_git = target)
where encode(name, 'escape') like '%.gemspec'
order by id desc
limit 100;"""
GEMSPECS_DIR = os.path.join(BASE_DIR, 'gemspecs')
GEMSPEC_LIST_PATH = os.path.join(BASE_DIR, 'gemspec_list.csv')

objstorage_client = RemoteObjStorage(
    url='http://uffizi.internal.softwareheritage.org:5003/')

def get_gemspec_list():
    if os.path.isfile(GEMSPEC_LIST_PATH):
        print('Using cached gemspec list')
        return
    else:
        print('Getting gemspec list')
        csv = subprocess.check_output([
            'psql', 'service=swh-replica', '-c', GEMSPEC_LIST_QUERY,
            '-t', '-A', '-F,'])
        print('Done')
        with open(GEMSPEC_LIST_PATH, 'wb') as fd:
            fd.write(csv)

def download_gemspecs():
    with open(GEMSPEC_LIST_PATH) as fd:
        for (name, sha1) in csv.reader(fd):
            download_gemspec(name, sha1)

def download_gemspec(name, sha1):
    path = os.path.join(GEMSPECS_DIR, '{}_{}'.format(name, sha1))
    if os.path.isfile(path):
        print('{} {}:\tskipped (already have it)'.format(name, sha1))
        return
    try:
        obj = objstorage_client.get(sha1)
    except ObjNotFoundError:
        print('{} {}:\tnot in objstorage'.format(sha1, name))
        return
    else:
        print('{} {}:\tdownloaded'.format(sha1, name))
    with open(path, 'wb') as fd:
        fd.write(obj)

os.makedirs(GEMSPECS_DIR, exist_ok=True)
get_gemspec_list()
download_gemspecs()
