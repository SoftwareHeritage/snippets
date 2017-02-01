# load testing with locust.io #

This directory contains data and configuration to allow load testing with
locust.io.

## Setting up locustio ##

Create a (Python 2) virtual environment (once):

`virtualenv -p /usr/bin/python2 venv`

Activate the environment:

`./venv/bin/activate`

Install locust.io (once):

`pip install locustio`

## Running locustio ##

Our webapp is behind HTTP basic authentication. We need to pass the variables
`SWH_USER` and `SWH_PASS` to the locust script:

`env SWH_USER=<foo> SWH_PASS=<bar> locust`

Once locust is running, you can go to `http://localhost:8089/` and launch the
swarm using the web interface.
