from urllib.parse import quote

import sys

file = "origins.csv"

f = open(file)
lines = f.readlines()

for line in lines:
    url = quote(line, safe='')
    print(url)

f.close()