import configparser
from urllib.parse import quote
from swh.web.client.client import WebAPIClient
import sys

config = configparser.ConfigParser()
config.read('config.ini')

token = config.get('SWH_Auth', 'token')

# Outputs a list of url-encoded origins from a string search parameter

cli = WebAPIClient(bearer_token=token)

query = sys.argv[1]
resp = cli.origin_search(query, limit=1000)

nb_origins = 0

for origin in resp:
    print(f"{quote(origin['url'], safe='')}")
    nb_origins += 1

print(f"{nb_origins} origins")

