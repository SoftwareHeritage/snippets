
from functools import lru_cache


def paginate(query, args, stop):
    """perform a query paginating through results until stop condition is met

    """
    after = None
    keep_going = True
    while keep_going:
        r = query(**args, after=after)
        if not(r['data']):
            break
        for item in r['data']:
            if stop(item):
                keep_going = False
                break
            yield item

        after = r['cursor']['after']


@lru_cache()
def lookup_repo(phab, repo_phid):
    """lookup Phabricator repository by PHID

    """
    if repo_phid:
        return phab.phid.query(phids=[repo_phid])[repo_phid]
    else:
        return None  # stacked diffs do not have an associated repo


def pp_repo(repo):
    """pretty print a short name for a given repository

    """
    if repo:
        return repo['uri'].split('/')[-2]
    else:
        return 'None'


@lru_cache()
def whoami(phab):
    """return current user's PHID

    """
    return phab.user.whoami()['phid']


def print_tasks(phab, tasks):
    """print a brief list of Phabricator tasks, with some context

    Args:
        phab: Phabricator instance
        tasks(iterable): tasks to be printed
    """
    for t in tasks:
        print('- T{id} | {status} | {name}'.format(
            id=t['id'],
            status=t['fields']['status']['value'],
            name=t['fields']['name']))


def print_commits(phab, commits):
    """print a list of Phabricator commits, with some context

    Args:
        phab: Phabricator instance
        commits(iterable): commits to be printed
    """
    for c in commits:
        repo = lookup_repo(phab, c['fields']['repositoryPHID'])
        print('- {id} | {repo} | {msg}'.format(
            id=c['fields']['identifier'][:12],
            repo=pp_repo(repo),
            msg=c['fields']['message'].split('\n')[0]))


def print_diffs(phab, reviews):
    """print a list of Phabricator diffs, with some context

    Args:
        phab: Phabricator instance
        reviews(iterable): diffs to be printed
    """
    for r in reviews:
        repo = lookup_repo(phab, r['fields']['repositoryPHID'])
        print('- https://forge.softwareheritage.org/D{id} | {repo} | {title}'.format(
            id=r['id'],
            repo=pp_repo(repo),
            title=r['fields']['title']))
