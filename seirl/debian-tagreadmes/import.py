import aiohttp
import asyncio
import concurrent.futures
import gzip
import hashlib
import io
import logging
import subprocess
import sys
import tempfile
import tqdm

from debian.deb822 import Sources, Packages, Deb822
from pathlib import Path
from peewee import Model, TextField, CharField, ForeignKeyField
from playhouse.fields import ManyToManyField
from playhouse.sqlite_ext import SqliteExtDatabase


MIRROR = 'http://ftp.fr.debian.org/debian'
RELEASE = 'jessie'
BASE_URL = '{mirror}/dists/{release}'.format(mirror=MIRROR,
                                                    release=RELEASE)
PKG_LIST = {}
SRC_LIST = {}

README_FILES = {
    'readme',
    'readme.markdown',
    'readme.mdown',
    'readme.mkdn',
    'readme.md',
    'readme.textile',
    'readme.rdoc',
    'readme.org',
    'readme.creole',
    'readme.mediawiki',
    'readme.wiki',
    'readme.rst',
    'readme.asciidoc',
    'readme.adoc',
    'readme.asc',
    'readme.pod',
    'README',
    'README.markdown',
    'README.mdown',
    'README.mkdn',
    'README.md',
    'README.textile',
    'README.rdoc',
    'README.org',
    'README.creole',
    'README.mediawiki',
    'README.wiki',
    'README.rst',
    'README.asciidoc',
    'README.adoc',
    'README.asc',
    'README.pod'
}


db = SqliteExtDatabase('debian_readme.db')

class BaseModel(Model):
    class Meta:
        database = db


class Tag(BaseModel):
    tag = TextField(unique=True)


class ReadmeFile(BaseModel):
    sha1 = CharField(unique=True)


class ReadmeTag(BaseModel):
    readme = ForeignKeyField(ReadmeFile)
    tag = ForeignKeyField(Tag)

    class Meta:
        indexes = ((('readme', 'tag'), True),)


class Package(BaseModel):
    name = TextField(unique=True)

    # this should be a manytomany...
    #readme = ForeignKeyField(ReadmeFile, related_name='packages')


db.connect()
db.create_tables([Tag, ReadmeFile, ReadmeTag, Package], safe=True)


def sha1file(path):
    BUF_SIZE = 2 ** 22
    sha1 = hashlib.sha1()
    with path.open('rb') as f:
        while True:
            data = f.read(BUF_SIZE)
            if not data:
                break
            sha1.update(data)
    return sha1.digest()


async def communicate(cmdline, data=None, **kwargs):
    logging.debug('Running %s', ' '.join(cmdline))
    proc = await asyncio.create_subprocess_exec(
        *cmdline, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, **kwargs)
    stdout, stderr = await proc.communicate(data)
    retcode = await proc.wait()
    return retcode, stdout, stderr


async def getdeb822(session, url, cls=Deb822):
    res = {}
    async with session.get(url) as resp:
        content = await resp.read()
        with gzip.GzipFile(fileobj=io.BytesIO(content)) as gf:
            content = gf.read()
        for src in cls.iter_paragraphs(content.decode()):
            res[src['Package']] = src
    return res



async def pkg_list(session, group):
    sources = '{url}/{group}/source/Sources.gz'.format(url=BASE_URL,
                                                       group=group)
    packages = '{url}/{group}/binary-amd64/Packages.gz'.format(url=BASE_URL,
                                                               group=group)
    SRC_LIST.update(await getdeb822(session, sources, cls=Sources))
    PKG_LIST.update(await getdeb822(session, packages, cls=Packages))


def handle_file(pkgname, f, tags):
    tags = (t.strip() for t in tags.split(','))
    tags_entries = [Tag.get_or_create(tag=tagname)[0] for tagname in tags]

    sha1 = sha1file(f)
    readme, _ = ReadmeFile.get_or_create(sha1=sha1)

    for te in tags_entries:
        rt, _ = ReadmeTag.get_or_create(tag=te, readme=readme)

    package, _ = Package.get_or_create(name=pkgname)#, readme=readme)


async def handle_package(package_name, sem):
    pkg = PKG_LIST[package_name]

    src = SRC_LIST[pkg['Source'].split()[0] if 'Source' in pkg else package_name]
    dsc = next(x for x in src['Files'] if x['name'].endswith('.dsc'))['name']
    directory = src['Directory']
    url_dsc = '{mirror}/{directory}/{dsc}'.format(mirror=MIRROR,
                                                  directory=directory, dsc=dsc)
    async with sem:
        with tempfile.TemporaryDirectory(prefix='debianreadme',
                                         dir='/srv/hdd/tmp') as tdir:
            await communicate(['dget', url_dsc], cwd=tdir)
            extract_root = Path(tdir)
            source_folder = next((d for d in extract_root.iterdir()
                                  if d.is_dir()), None)
            if source_folder is not None:
                for f in source_folder.iterdir():
                    if f.is_file() and f.name in README_FILES:
                        await asyncio.get_event_loop().run_in_executor(None,
                            handle_file, package_name, f, pkg['Tag'])


async def handle_package_pg(package_name, sem, pbar):
    await handle_package(package_name, sem)
    pbar.update(1)


async def main():
    print('Loading packages… ', end='', flush=True)
    with aiohttp.ClientSession() as session:
        await pkg_list(session, 'main')
        await pkg_list(session, 'contrib')
        await pkg_list(session, 'non-free')
    print('done.')

    print('Filtering packages… ', end='', flush=True)
    todo = [k for k, v in PKG_LIST.items()
            if 'Tag' in v
            and not Package.select().where(Package.name == k).exists()]
    print('done.')

    semaphore = asyncio.BoundedSemaphore(64)
    pbar = tqdm.tqdm(total=len(todo))
    tasks = [handle_package_pg(pkg, semaphore, pbar) for pkg in todo]
    await asyncio.gather(*tasks)


if __name__ == '__main__':
    # One worker to have sequential database access outside the main loop
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)

    loop = asyncio.get_event_loop()
    loop.set_default_executor(executor)
    loop.run_until_complete(main())
    loop.close()
