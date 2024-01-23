#!/usr/bin/env python3

# Copyright (C) 2024  The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information

import logging
import os
import re
import subprocess
import tempfile

import chardet

logger = logging.getLogger(__name__)

project_regexp = re.compile(
    r":pserver:anonymous@cvs.osdn.net:/cvsroot/([^ ]+) co modulename"
)

input_file = "pserver-anonymous-cvs.osdn.net-cvsroot-all-from-projects-all-scm.txt"


def get_module_names(cvs_output):
    result = chardet.detect(cvs_output)
    return [
        module
        for module in ret.stdout.decode(result["encoding"]).split("\n")
        if module not in ("CVSROOT", "")
    ]


for cvs_info in open(input_file, "r").readlines():
    project_name = project_regexp.match(cvs_info).group(1)
    with tempfile.TemporaryDirectory() as tmp_dir:
        pserver = f":pserver:anonymous@cvs.osdn.net:/cvsroot/{project_name}"
        ret = subprocess.run(
            [
                "cvs",
                f"-d{pserver}",
                "checkout",
                "-l",
                f"-d{project_name}",
                ".",
            ],
            cwd=tmp_dir,
            capture_output=True,
        )
        if ret.returncode == 0:
            ret = subprocess.run(
                ["cvs", "ls"],
                cwd=os.path.join(tmp_dir, project_name),
                capture_output=True,
            )
            modules = get_module_names(ret.stdout)
            for module in modules:
                print(
                    f"pserver://anonymous@cvs.osdn.net/cvsroot/{project_name}/{module}"
                )
        else:
            result = chardet.detect(ret.stderr)
            logger.warning(
                "Failed to checkout %s\n%s",
                pserver,
                ret.stderr.decode(result["encoding"]),
            )
