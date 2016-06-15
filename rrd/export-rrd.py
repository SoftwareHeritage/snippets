#!/usr/bin/env python

"""Script to execute the export of softwareheritage's rrds data.

"""

import click
import os
import subprocess

DIRPATH='/var/lib/munin/softwareheritage.org/'
FILENAME_PATTERN="prado.softwareheritage.org-softwareheritage_objects_softwareheritage-###-g.rrd"
# The data source used to create the rrd file
DS=42

ENTITIES=[
    "content",
    "directory_entry_dir",
    "directory_entry_file",
    "directory_entry_rev",
    "directory",
    "entity",
    "occurrence_history",
    "origin",
    "person",
    "project",
    "release",
    "revision",
    "revision_history",
    "skipped_content",
    "visit",
]

@click.command()
@click.option('--dirpath', default=DIRPATH)
def main(dirpath):
    cmd=''
    for entity in ENTITIES:
        filename = FILENAME_PATTERN.replace('###', entity)
        filepath = os.path.join(dirpath, filename)

        if os.path.exists(filepath):
            cmd += ''' DEF:out-%s1="%s":%s:AVERAGE XPORT:out-%s1:"%s-avg" DEF:out-%s2="%s":%s:MIN XPORT:out-%s2:"%s-min" DEF:out-%s3="%s":%s:MAX XPORT:out-%s3:"%s-max"''' % (
                 entity, filepath, DS, entity, entity,
                 entity, filepath, DS, entity, entity,
                 entity, filepath, DS, entity, entity)

    run_cmd = 'rrdtool xport --json %s' % (cmd, )

    subprocess.check_call(run_cmd, shell=True)


if __name__ == '__main__':
    main()
