#!/usr/bin/env python3

#OAR -d /home/kirchgem/2025-06-15-testnodesdispatching
#OAR -l /nodes=10/core=1,walltime=00:01:00
#OAR --name test-dispatching
#OAR --project pr-swh-codecommons
#OAR --stdout stdout.log
#OAR --stderr stderr.log

"""
This driver script tries to find if it's the head node, or called as a sub-process.

From the head node (ie when called without any argument)
 * it will start [THREADS_PER_HOST] threads *per machine*  in $OAR_NODE_FILE
 * the job generator should be adjusted depending on what to do
 * each thread will call (and wait) `ssh [host] __file__ param` for each param from the generator
   so __file__ path should be the same on all machines (use your $HOME)

When called with an argument, the script assumes we're a worker node so it starts the job from the parameter
"""
import logging
from time import perf_counter
from sys import argv, stdout
from os import environ
from subprocess import run
from threading import Thread
from queue import Queue, Empty
import socket

log = logging.getLogger()
log.setLevel(logging.DEBUG)

HOSTNAME = socket.gethostname()


######### real things to do go here. job_generator will only run in the head node

THREADS_PER_HOST = 2

def params_generator():
    for i in range(100):
        yield str(i)

def worker_function(param):
    from random import random
    from time import sleep
    log.info("starting worker function(%s)", param)
    sleep(random())
    log.info("finished worker function(%s)", param)

########## wrappers

def setup_logging(hostname):
    ch = logging.StreamHandler(stdout)
    ch.setLevel(logging.DEBUG)
    formatter = logging.Formatter(
        "%(asctime)s - " + hostname + " - %(levelname)s - %(message)s"
    )
    ch.setFormatter(formatter)
    log.addHandler(ch)

def node_driver(q, node_name):
    while True:
        try:
            p = q.get_nowait()
            params = ["oarsh", node_name, __file__, p]
            run(params, stdout=stdout, stderr=stdout)
        except Empty:
            return

def main_head():
    node_file = environ.get("OAR_NODE_FILE")
    with open(node_file) as f:
        nodes = set(f.readlines())
    q = Queue()
    for i in params_generator():
        q.put(i)
    log.info("Loaded nodes list and parameters queue")
    driver_threads = []
    for n in range(THREADS_PER_HOST):
        for node in nodes:
            driver_thread = Thread(target=node_driver, args=(q, node.strip()))
            driver_threads.append(driver_thread)
            driver_thread.start()
    for t in driver_threads:
        t.join()

if __name__ == "__main__":
    global_start = perf_counter()
    if len(argv) == 1:
        HOSTNAME += "(head)"
    setup_logging(HOSTNAME)

    if len(argv) > 1:
        worker_function(argv[1])
    else:
        log.info("Hello")
        main_head()
        log.info("Finished in %fs", perf_counter() - global_start)
