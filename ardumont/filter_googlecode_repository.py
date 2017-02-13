#!/usr/bin/env python3

# Copyright (C) 2017  The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information


import click
import os
import json
import sys


def repo_type_match(project_metadata_filepath, repo_type):
    """Ensure a given repository whose information are stored in
       project_metadata_filepath reference a repoType entry as 'repo_type'
       value. If this is the case, the name of the project is returned.

       Expected json format of the project_metadata_filepath as something like:
       {"domain":"apache-extras.org",
        "name":"airavata-gsoc-sandbox",
        "summary":"Sandbox for Airavata GSoC Projects",
        "description":"Apache Airavata is a software toolkit to
                       compose, manage, execute, and monitor small to large scale
                       applications and workflows on computational resources. This
                       project is a sandbox area for google summer of code
                       participants.",
        "stars":1,
        "license":"asf20",
        "contentLicense":"",
        "labels":["airavata","Services"],
        "creationTime":1339404742000,
        "repoType":"svn",
        "subrepos":[],
        "hasSource":true,
        "ancestorRepo":"",
        "logoName":"",
        "movedTo":""
       }

    """
    with open(project_metadata_filepath, 'r') as f:
        data = json.loads(f.read())

        if data['repoType'] == repo_type:
            return data['name']


def project_info(project_metadata_filepath, filter_repository_type):
    """Read and dump information on repository if the repository's type
       match filter_repository_type.

       Expects a project.json file being present in the folder path
       read from stdin.

       If that project.json contains a repoType entry matching
       filter_repository_type, then yield the project's old googlecode
       svn url and the project_name

    """
    name = repo_type_match(
        project_metadata_filepath, filter_repository_type)

    if name:
        url = 'https://%s.googlecode.com' % name
        return {
            'url': url,
            'name': name,
        }


@click.command()
@click.option('--filter-repository-type',
              default='git',
              help='''Filtering repository type.
                      Possible values are: git, svn, hg''')
@click.pass_context
def run(ctx, filter_repository_type):
    """Given fed filepath, dump information on repository encountered if
       the repository's type match filter_repository_type.

    """
    possible_filters = {'git', 'hg', 'svn'}
    if filter_repository_type not in possible_filters:
        print('Error: Possible filters should be in %s\n\n%s' % (
            possible_filters, ctx.get_help()), file=sys.stderr)
        sys.exit(1)

    for line in sys.stdin:
        line = line.strip()

        project_fullpath = line
        project_dir = os.path.dirname(line)
        project_metadata_filepath = '%s/project.json' % project_dir

        try:
            project = project_info(
                project_metadata_filepath, filter_repository_type)

            if project:
                print('%s %s' % (
                    project['url'],
                    project_fullpath))

        except Exception as e:
            print('Error: %s' % str(e), file=sys.stderr)


if __name__ == '__main__':
    run()
