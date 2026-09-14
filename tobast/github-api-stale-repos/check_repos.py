"""Demo: Github does return repos that do not exist (anymore) when querying
/repositories on the API."""

import requests
import typing as t

API_BASE_URL = "https://api.github.com"


def _token() -> str:
    with open("./.token", "r") as h:
        return h.read().strip()


def github_headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {_token()}",
        "X-GitHub-Api-Version": "2026-03-10",
    }


def create_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(github_headers())
    return session


_session = create_session()


def get_repos(since: int) -> list[dict]:
    res = _session.get(
        API_BASE_URL + "/repositories",
        headers=github_headers(),
        params={"since": since},
    )
    repos = res.json()
    return repos


# eg. repo #1046300106 'https://github.com/JohnjyWolfeArlene/Krueger' 404s
def repo_exists(url) -> bool:
    res = _session.head(url)
    return res.status_code == 200


def demo():
    demo_repo_id = 1046300106
    repos = get_repos(since=demo_repo_id - 1)
    for repo in repos:
        if repo["id"] == demo_repo_id:
            print(f"Got repo #{demo_repo_id}")
            assert repo["html_url"] == "https://github.com/JohnjyWolfeArlene/Krueger"
            print(f"URL: {repo['html_url']}")
            query = _session.get(repo["html_url"])
            print(f"Response: {query.status_code}")
            break
