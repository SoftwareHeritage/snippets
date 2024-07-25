import json
import sys

file = sys.argv[1]

f = open(file)

data = json.load(f)

i = 0

for d in data:
    license = d['license']
    if license:
        license = d['license']['name']
    print(f"{d['name']} : {license}")
    i+=1

print(i)

f.close