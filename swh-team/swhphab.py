
from functools import lru_cache


def paginate(query, args, stop):
    """perform a query paginating through results until stop condition is met

    """
    def do_query():
        after = '0'
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

    return list(do_query())


@lru_cache()
def lookup_repo(phab, repo_phid):
    """lookup Phabricator repository by PHID

    """
    return phab.phid.query(phids=[repo_phid])[repo_phid]


def pp_repo(repo):
    """pretty print a short name for a given repository

    """
    return repo['uri'].split('/')[-2]


@lru_cache()
def whoami(phab):
    """return current user's PHID

    """
    return phab.user.whoami()['phid']
