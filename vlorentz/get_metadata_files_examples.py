import csv
import os
import os.path
import subprocess

from swh.objstorage.api.client import RemoteObjStorage
from swh.objstorage.exc import ObjNotFoundError

BASE_DIR = os.path.expanduser('~/datasets/')

LIST_QUERY = """
select encode(name, 'escape'), encode(sha1, 'hex')
from directory_entry_file
inner join content on (sha1_git = target)
where name = decode('%s', 'escape')
order by id desc
limit 100;"""
GEMSPEC_LIST_QUERY = """
select encode(name, 'escape'), encode(sha1, 'hex')
from directory_entry_file
inner join content on (sha1_git = target)
where encode(name, 'escape') like '%.gemspec'
order by id desc
limit 100;"""
GEMSPECS_DIR = os.path.join(BASE_DIR, 'gemspecs')

objstorage_client = RemoteObjStorage(
    url='http://uffizi.internal.softwareheritage.org:5003/')


class ExamplesDownloader:
    def __init__(self, category_name):
        self.category_name = category_name
        self.csv_path = os.path.join(BASE_DIR, category_name + '_list.csv')
        self.dir = os.path.join(BASE_DIR, category_name)
        os.makedirs(self.dir, exist_ok=True)

    def download_files(self):
        with open(self.csv_path) as fd:
            for (name, sha1) in csv.reader(fd):
                self.download_file(name, sha1)

    def download_file(self, name, sha1):
        path = os.path.join(self.dir, '{}_{}'.format(name, sha1))
        if os.path.isfile(path):
            print('{} {}:\tskipped (already have it)'.format(sha1, name))
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

    def get_list_if_needed(self):
        if os.path.isfile(self.csv_path):
            print('Using cached list for {}'.format(self.category_name))
            return
        else:
            print('Requesting list for {}'.format(self.category_name))
            csv = self.get_list()
            with open(self.csv_path, 'wb') as fd:
                fd.write(csv)

    def run(self):
        self.get_list_if_needed()
        self.download_files()


class FixedNameExamplesDownloader(ExamplesDownloader):
    def __init__(self, category_name, filename):
        super().__init__(category_name)
        self.filename = filename

    def get_list(self):
        return subprocess.check_output([
            'psql', 'service=swh-replica', '-c', LIST_QUERY % self.filename,
            '-t', '-A', '-F,'])


class GemspecExamplesDownloader(ExamplesDownloader):
    def __init__(self):
        super().__init__('gemspec')

    def get_list(self):
        return subprocess.check_output([
            'psql', 'service=swh-replica', '-c', GEMSPEC_LIST_QUERY,
            '-t', '-A', '-F,'])


GemspecExamplesDownloader().run()
FixedNameExamplesDownloader('pkginfo', 'PKG-INFO').run()
