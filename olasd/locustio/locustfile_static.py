import os
import random

from locust import HttpLocust, TaskSet, task

import swh_data
swh_data.read_all_data()


class BaseUserBehavior(TaskSet):
    headers = {}
    base_name = 'base'

    @staticmethod
    def random(data_type):
        return random.choice(swh_data.DATA[data_type])

    def get(self, *args, **kwargs):
        kwargs['headers'] = self.headers
        if 'name' in kwargs:
            kwargs['name'] = '%s:%s' % (self.base_name,
                                        kwargs['name'])
        return self.client.get(*args, **kwargs)


class BrowseUserBehavior(BaseUserBehavior):
    base_name = 'browse'
    headers = {'Accept': 'text/html'}

    @task(1)
    def base_index(self):
        self.client.get('/')

    @task(1)
    def api_index(self):
        self.client.get('/api/')

    @task(1)
    def api_1_index(self):
        self.client.get('/api/1/')


class UserBehavior(TaskSet):
    tasks = {
        BrowseUserBehavior: 30,
    }


class UserLocust(HttpLocust):
    task_set = UserBehavior
    host = 'https://archive.softwareheritage.org'
    min_wait = 100
    max_wait = 1000
