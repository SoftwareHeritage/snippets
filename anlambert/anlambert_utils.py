# Copyright (C) 2025  The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information

import logging
import os
import shutil

import requests
from dulwich.errors import GitProtocolError
from dulwich.porcelain import clone
from swh.core.retry import (
    MAX_NUMBER_ATTEMPTS,
    WAIT_EXP_BASE,
    http_retry,
    retry_if_exception,
)
from tenacity import retry as tenacity_retry
from tenacity.before_sleep import before_sleep_log
from tenacity.stop import stop_after_attempt
from tenacity.wait import wait_exponential


logger = logging.getLogger(os.path.basename(__file__))
session = requests.Session()


@http_retry(before_sleep=before_sleep_log(logger, logging.WARNING))
def url_get(url):
    response = session.get(url)
    response.raise_for_status()
    return response


def is_git_throttling_exception(exc):
    return isinstance(exc, GitProtocolError) and "unexpected http resp 429" in str(exc)


def git_retry(
    retry=lambda retry_state: retry_if_exception(
        retry_state, is_git_throttling_exception
    ),
    wait=wait_exponential(exp_base=WAIT_EXP_BASE),
    stop=stop_after_attempt(max_attempt_number=MAX_NUMBER_ATTEMPTS),
    **retry_args,
):
    return tenacity_retry(retry=retry, wait=wait, stop=stop, reraise=True, **retry_args)


@git_retry(before_sleep=before_sleep_log(logger, logging.WARNING))
def clone_repository(repo_url, target_dir):
    shutil.rmtree(os.path.join(target_dir, ".git"), ignore_errors=True)
    clone(repo_url, target_dir)
