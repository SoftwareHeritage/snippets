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
SOURCES = 'http://sources.debian.net'
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


class Package(BaseModel):
    name = TextField(unique=True)


class PackageTag(BaseModel):
    package = ForeignKeyField(Package)
    tag = ForeignKeyField(Tag)

    class Meta:
        indexes = ((('package', 'tag'), True),)


class Readme(BaseModel):
    name = TextField()
    sha256 = CharField(max_length=256)
    package = ForeignKeyField(Package, related_name='readmes')


db.connect()
db.create_tables([Tag, Package, PackageTag, Readme], safe=True)


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


def handle_file(pkgname, readme_name, sha256, tags):
    tags = (t.strip() for t in tags.split(','))
    tags_entries = [Tag.get_or_create(tag=tagname)[0] for tagname in tags]

    package, _ = Package.get_or_create(name=pkgname)
    for te in tags_entries:
        pt, _ = PackageTag.get_or_create(tag=te, package=package)

    readme, _ = Readme.get_or_create(name=readme_name, sha256=sha256, package=package)


async def handle_package(package_name, session, sem):
    pkg = PKG_LIST[package_name]

    src = SRC_LIST[pkg['Source'].split()[0] if 'Source' in pkg else package_name]
    url_index = '{sources}/api/src/{package}/{version}/'.format(
        sources=SOURCES, package=src['Package'], version=src['Version'])
    async with sem:
        data = await session.get(url_index)
        index = await data.json()

        # Bug with non-ascii file paths
        if 'error' in index and index['error'] == 500:
            tqdm.tqdm.write('error 500 with package {}'.format(package_name))
            return

        for f in index['content']:
            if f['type'] == 'file' and f['name'] in README_FILES:
                url_content = '{url_index}{fname}/'.format(url_index=url_index,
                                                           fname=f['name'])
                content = await (await session.get(url_content)).json()

                # Broken symlink
                if 'error' in content and content['error'] == 404:
                    tqdm.tqdm.write('broken symlink for {} in {}'.format(
                        f['name'], package_name))
                    continue

                await asyncio.get_event_loop().run_in_executor(
                    None, handle_file, package_name, f['name'],
                    content['checksum'], pkg['Tag'])


async def handle_package_pg(package_name, session, sem, pbar):
    await handle_package(package_name, session, sem)
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

    semaphore = asyncio.BoundedSemaphore(10)
    pbar = tqdm.tqdm(total=len(todo))
    with aiohttp.ClientSession() as session:
        tasks = [handle_package_pg(pkg, session, semaphore, pbar) for pkg in todo]
        await asyncio.gather(*tasks)


if __name__ == '__main__':
    # One worker to have sequential database access outside the main loop
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)

    loop = asyncio.get_event_loop()
    loop.set_default_executor(executor)
    loop.run_until_complete(main())
    loop.close()
