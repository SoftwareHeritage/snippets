#!/usr/bin/env python

"""Script to execute the export of softwareheritage's rrds data.

"""

import click
import json
import os
import subprocess


DIRPATH='/var/lib/munin/softwareheritage.org/'
FILENAME_PATTERN="prado.softwareheritage.org-softwareheritage_objects_softwareheritage-###-g.rrd"
# The data source used at rrd creation time
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


def compute_cmd(dirpath):
    """Compute the command to execute to retrieve the needed data.

    Returns:
        The command as string.

    """
    cmd=''
    for entity in ENTITIES:
        filename = FILENAME_PATTERN.replace('###', entity)
        filepath = os.path.join(dirpath, filename)

        if os.path.exists(filepath):
            cmd += ''' DEF:out-%s1="%s":%s:AVERAGE XPORT:out-%s1:"%s-avg" DEF:out-%s2="%s":%s:MIN XPORT:out-%s2:"%s-min" DEF:out-%s3="%s":%s:MAX XPORT:out-%s3:"%s-max"''' % (
                 entity, filepath, DS, entity, entity,
                 entity, filepath, DS, entity, entity,
                 entity, filepath, DS, entity, entity)

    return 'rrdtool xport --json --start 1431436580 --step 86400 %s' % (cmd, )


def retrieve_json(cmd):
    """Given the cmd command, execute and returns the right json format.

    Args:
        cmd: the command to execute to retrieve the desired json.

    Returns:
        The desired result as json string.
    """
    cmdpipe = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
    data = ''
    while True:
        line = cmdpipe.stdout.readline()
        if not line:
            break
        # Hack: the json outputd is not well-formed...
        line = line.replace('\'', '"')
        line = line.replace('about: ', '"about": ')
        line = line.replace('meta:', '"meta": ')
        data += line

    cmdpipe.stdout.close()
    return data


@click.command()
@click.option('--dirpath', default=DIRPATH)
def main(dirpath):
    # Delegate the execution to the system
    run_cmd = compute_cmd(dirpath)
    json_data = retrieve_json(run_cmd)

    # to make sure the json is well-formed
    data = json.loads(json_data)
    # TODO: prepare the json appropriately here
    print(json.dumps(data))


if __name__ == '__main__':
    main()
