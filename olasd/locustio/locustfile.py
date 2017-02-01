import os
import random

from locust import HttpLocust, TaskSet, task

import swh_data
swh_data.read_all_data()


class BaseUserBehavior(TaskSet):
    headers = {}
    auth = (os.getenv('SWH_USER'), os.getenv('SWH_PASS'))
    base_name = 'base'

    @staticmethod
    def random(data_type):
        return random.choice(swh_data.DATA[data_type])

    def get(self, *args, **kwargs):
        kwargs['auth'] = self.auth
        kwargs['headers'] = self.headers
        if 'name' in kwargs:
            kwargs['name'] = '%s:%s' % (self.base_name,
                                        kwargs['name'])
        return self.client.get(*args, **kwargs)

    @task(10)
    def content_sha1(self):
        c = self.random('content')
        self.get(
            '/api/1/content/sha1:%s/' % c['sha1'],
            name='/api/1/content/sha1:[sha1]/',
        )

    @task(10)
    def content_sha1_git(self):
        c = self.random('content')
        self.get(
            '/api/1/content/sha1_git:%s/' % c['sha1_git'],
            name='/api/1/content/sha1_git:[sha1_git]/',
        )

    @task(10)
    def content_sha256(self):
        c = self.random('content')
        self.get(
            '/api/1/content/sha256:%s/' % c['sha256'],
            name='/api/1/content/sha256:[sha256]/',
        )

    @task(10)
    def directory(self):
        d = self.random('directory')
        self.get(
            '/api/1/directory/%s/' % d['id'],
            name='/api/1/directory/[sha1_git]/',
        )

    @task(10)
    def revision(self):
        r = self.random('revision')
        self.get(
            '/api/1/revision/%s/' % r['id'],
            name='/api/1/revision/[sha1_git]/',
        )

    @task(10)
    def release(self):
        r = self.random('release')
        self.get(
            '/api/1/release/%s/' % r['id'],
            name='/api/1/release/[sha1_git]/',
        )

    @task(10)
    def person(self):
        p = self.random('person')
        self.get(
            '/api/1/person/%d/' % p['id'],
            name='/api/1/person/[id]/',
        )

    @task(10)
    def origin(self):
        o = self.random('origin_visit')
        self.get(
            '/api/1/origin/%d/' % o['origin'],
            name='/api/1/origin/[id]/',
        )

    @task(10)
    def origin_visit(self):
        o = self.random('origin_visit')
        self.get(
            '/api/1/origin/%d/visit/%d/' % (o['origin'], o['visit']),
            name='/api/1/origin/[id]/visit/[id]',
        )


class BrowseUserBehavior(BaseUserBehavior):
    base_name = 'browse'
    headers = {'Accept': 'text/html'}

    @task(1)
    def base_index(self):
        self.client.get('/', auth=self.auth)

    @task(1)
    def api_index(self):
        self.client.get('/api/', auth=self.auth)

    @task(1)
    def api_1_index(self):
        self.client.get('/api/1/', auth=self.auth)


class APIUserBehavior(BaseUserBehavior):
    base_name = 'json'
    headers = {'Accept': 'application/json'}


class UserBehavior(TaskSet):
    tasks = {
        APIUserBehavior: 10,
        BrowseUserBehavior: 30,
    }


class UserLocust(HttpLocust):
    task_set = UserBehavior
    host = 'https://archive.softwareheritage.org'
    min_wait = 100
    max_wait = 1000
