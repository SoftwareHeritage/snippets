#!/usr/bin/env python

"""Script to execute the export of softwareheritage's rrds data.

"""

import click
import json
import os
import subprocess
import time


DIRPATH='/var/lib/munin/softwareheritage.org/'
FILENAME_PATTERN="prado.softwareheritage.org-softwareheritage_objects_softwareheritage-###-g.rrd"
# The data source used at rrd creation time
DS=42

ENTITIES=[
    "content",
    "origin",
    "revision",
    # "directory_entry_dir",
    # "directory_entry_file",
    # "directory_entry_rev",
    # "directory",
    # "entity",
    # "occurrence_history",
    # "person",
    # "project",
    # "release",
    # "revision_history",
    # "skipped_content",
    # "visit",
]


def compute_cmd(dirpath,
                step=86400,
                with_avg=True,
                with_min=True,
                with_max=True):
    """Compute the command to execute to retrieve the needed data.

    Returns:
        The command as string.

    """
    cmd=''
    for entity in ENTITIES:
        filename = FILENAME_PATTERN.replace('###', entity)
        filepath = os.path.join(dirpath, filename)

        if os.path.exists(filepath):
            if with_avg:
                cmd += ' DEF:out-%s1="%s":%s:AVERAGE XPORT:out-%s1:"%s-avg"' % (
                    entity, filepath, DS, entity, entity)

            if with_min:
                cmd += ' DEF:out-%s2="%s":%s:MIN XPORT:out-%s2:"%s-min"' % (
                    entity, filepath, DS, entity, entity)

            if with_max:
                cmd += ' DEF:out-%s3="%s":%s:MAX XPORT:out-%s3:"%s-max"' % (
                    entity, filepath, DS, entity, entity)

    # 31536000 = (* 60 60 24 365) - 1 year back from now in seconds
    # return 'rrdtool xport --json --start -31536000 %s' % (cmd, )
    # 1434499200 == 2015-05-12T16:51:25+0200, the starting date

    starting_date_ts = int(time.mktime(
        time.strptime('2015-05-12T16:51:25Z', '%Y-%m-%dT%H:%M:%SZ')))
    return 'rrdtool xport --json --start %s --step %s %s' % (
        starting_date_ts, step, cmd)


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
    return json.loads(data)


def prepare_data(data):
    """Prepare the data with x,y coordinate.

    x is the time, y is the actual value.
    """
    # javascript has a ratio of 1000...
    step = data['meta']['step'] * 1000  # nb of milliseconds
    start_ts = data['meta']['start'] * 1000  # starting ts

    legends = data['meta']['legend']

    # The legends, something like
    # ["content-avg", "content-min", "content-max", "directory_entry_dir-avg", ...]
    r = {}
    day_ts = start_ts
    for day, values in enumerate(data['data']):
        day_ts += step
        for col, value in enumerate(values):
            legend_col = legends[col]
            l = r.get(legend_col, [])
            l.append((day_ts, value if value else 0))
            r[legend_col] = l

    return r


@click.command()
@click.option('--dirpath', default=DIRPATH, help="Default path to look for rrd files.")
@click.option('--step', default=86400, help="Compute the data step (default to 86400).")
@click.option('--avg/--noavg', default=True, help="Compute the average values (default to True).")
@click.option('--min/--nomin', default=False, help="Compute the min values (default to False).")
@click.option('--max/--nomax', default=False, help="Compute the max values (default to False).")
def main(dirpath, avg, min, max):
    # Delegate the execution to the system
    run_cmd = compute_cmd(dirpath, with_avg=avg, with_min=min, with_max=max)
    data = retrieve_json(run_cmd)

    # Format data
    data = prepare_data(data)

    print(json.dumps(data))


if __name__ == '__main__':
    main()
