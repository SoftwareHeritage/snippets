from flask import Flask
import os
import platform
app = Flask(__name__)

@app.route('/')
def hello_world():
    return f"Hello!\nversion:{os.environ['VERSION']}\nhostname:{platform.node()}\n"

@app.route('/count')
def count():
    try:
        with open("/data/count.txt", "r") as f:
            count = f.read()
    except:
        count = 0

    calls = count + 1

    with open("/data/count.txt", "w") as f:
        f.write(str(calls))

    return f"version:{os.environ['VERSION']}\nhostname:{platform.node()}: count={calls}"
