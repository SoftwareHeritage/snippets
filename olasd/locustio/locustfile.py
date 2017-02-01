import os
import random

from locust import HttpLocust, TaskSet, task

import swh_data
swh_data.read_all_data()


class UserBehavior(TaskSet):
    auth = (os.getenv('SWH_USER'), os.getenv('SWH_PASS'))

    @staticmethod
    def random(data_type):
        return random.choice(swh_data.DATA[data_type])

    @task(1)
    def base_index(self):
        self.client.get('/', auth=self.auth)

    @task(1)
    def api_index(self):
        self.client.get('/api/', auth=self.auth)

    @task(1)
    def api_1_index(self):
        self.client.get('/api/1/', auth=self.auth)

    @task(10)
    def content_sha1(self):
        c = self.random('content')
        self.client.get(
            '/api/1/content/sha1:%s/' % c['sha1'],
            name='/api/1/content/sha1:[sha1]/',
            auth=self.auth,
        )

    @task(10)
    def content_sha1_git(self):
        c = self.random('content')
        self.client.get(
            '/api/1/content/sha1_git:%s/' % c['sha1_git'],
            name='/api/1/content/sha1_git:[sha1_git]/',
            auth=self.auth,
        )

    @task(10)
    def content_sha256(self):
        c = self.random('content')
        self.client.get(
            '/api/1/content/sha256:%s/' % c['sha256'],
            name='/api/1/content/sha256:[sha256]/',
            auth=self.auth,
        )


class WebsiteUser(HttpLocust):
    task_set = UserBehavior
    host = 'https://archive.softwareheritage.org/'
    min_wait = 100
    max_wait = 1000
