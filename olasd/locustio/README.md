# load testing with locust.io #

This directory contains data and configuration to allow load testing with
locust.io.

## Setting up locustio ##

Create a (Python 2) virtual environment (once):

`virtualenv -p /usr/bin/python2 venv`

Activate the environment:

`. ./venv/bin/activate`

Install locust.io (once):

`pip install locustio pyzmq`

## Running locustio ##

`locust --client --master-host=<MASTER-HOST>`

Once locust is running, you can go to `http://MASTER-HOST:8089/` and launch the
swarm using the web interface.
