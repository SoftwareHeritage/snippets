from flask import Flask
import os
import platform

app = Flask(__name__)

@app.route('/')
def hello_world():
    return f"Hello!\nversion:{os.environ['VERSION']}\nhostname:{platform.node()}\n"

@app.route('/count')
def count():
    return f"version:{os.environ['VERSION']}\nhostname:{platform.node()}\nNot yet implemented\n"
