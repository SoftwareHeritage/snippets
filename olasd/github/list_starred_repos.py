#!/usr/bin/env python3

import sys
import time

import requests

API_SEARCH_URL = 'https://api.github.com/search/repositories'
REPOS_QUERY = 'stars:>=1000'


def get_page(api, query, page, credentials):
    req = requests.get(api, auth=credentials, params={
        'q': query,
        'sorted': 'stars',
        'page': page,
    })

    res = req.json()

    if 'items' not in res:
        print(res)
        return None

    urls = ['https://github.com/%s' % repo['full_name']
            for repo in req.json()['items']]

    return {
        'urls': urls,
        'links': req.links,
    }

if __name__ == '__main__':
    credentials = tuple(sys.argv[1:3])
    page = 1
    while True:
        res = get_page(API_SEARCH_URL, REPOS_QUERY, page, credentials)
        if not res:
            break
        for url in res['urls']:
            print(url)
        if not res['links'].get('next'):
            break
        page += 1
        time.sleep(5)
