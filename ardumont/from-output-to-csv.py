# Use sample:
# cat mercurial.output.txt | \
#     grep 'sensible-filter' | \
#     python3 -m from-output-to-csv

# The output of this command is designed to feed the
# `swh.scheduler.cli task schedule` subcommand


import ast
import click
import json
import sys


TYPES = {
    'mercurial': 'origin-update-hg',
    'mercurial-archive': 'origin-load-archive-hg',
    'svn': 'origin-update-svn',
    'svn-archive': 'swh-loader-mount-dump-and-load-svn-repository',
    'pypi': 'origin-update-pypi',
}


@click.command()
@click.option('--task-policy', default='oneshot', type=click.Choice([
                  'oneshot', 'recurring']),
              help="Task's policy")
@click.option('--task-type', default='mercurial', type=click.Choice(
    TYPES.keys()),
              help="Task's type")
def main(task_policy, task_type):
    """Given an output from kibana_fetch_logs, transform the input in csv
       format (; as delimiter) to ease back scheduling for those
       origins.

       The output format is of the form:
       <task-type>;<task-policy>;task-args;task-kwargs

       Then use of `swh.scheduler.cli schedule` subcommand.

       cat <output-of-this-command> | \
           python3 -m swh.mercurial.cli task schedule \
               --columns type \
               --columns policy \
               --columns args \
               --columns kwargs \
               --delimiter ';' -

    """
    for line in sys.stdin:
        line = line.rstrip()
        data = ast.literal_eval(line)

        _task_type = TYPES.get(task_type)
        _task_args = json.dumps(data['args'])

        kwargs = data['kwargs']

        # HACK: Should have been set earlier...
        if task_type in ['mercurial', 'mercurial-archive']:
            if 'visit_date' not in kwargs:
                kwargs['visit_date'] = 'Tue, 3 May 2016 17:16:32 +0200'

        _task_kwargs = json.dumps(kwargs)

        print(';'.join([_task_type, task_policy, _task_args, _task_kwargs]))


if __name__ == '__main__':
    main()
