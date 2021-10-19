import sys
import copy
import statistics
import pandas as pd
import matplotlib.pyplot as pl

from typing import List, Dict


def load_csv(filename: str) -> Dict[str, List]:
    template = {
        "unfiltered_count": [],
        "missing_duration": [],
        "filtered_count": [],
        "add_duration": [],
    }

    data = {
        "content": copy.deepcopy(template),
        "directory": copy.deepcopy(template),
        "skipped_content": copy.deepcopy(template),
        "revision": copy.deepcopy(template),
        "release": copy.deepcopy(template),
    }

    print("Loading:", filename)

    with open(filename) as f:
        content = f.read().splitlines()

    for line in content:
        fields = line.strip().split(";")
        # print(f"{l}")
        values = data[fields[0]]
        values["unfiltered_count"].append(int(fields[1]))
        values["missing_duration"].append(float(fields[2]))
        values["filtered_count"].append(int(fields[3]))
        values["add_duration"].append(float(fields[4]))

    return data


arg_count = len(sys.argv) - 1

files = []

for i in range(0, int(arg_count / 2)):
    name = str(sys.argv[i * 2 + 1])
    filename = str(sys.argv[i * 2 + 2])
    files.append([name, filename])

output = str(sys.argv[arg_count])

print(files)
print(output)

files_data = []
for f in files:
    files_data.append(load_csv(f[1]))

print("generating graphs...")

for type in ["content", "directory", "revision"]:

    print(type)

    for op in ["missing_duration", "add_duration"]:
        pl.close("all")
        graph_data = []

        quantiles = []
        for data in files_data:
            quantiles.append(statistics.quantiles(data[type][op], n=10))

        print(quantiles)

        for i in range(0, 9):
            q = []
            for quantile in quantiles:
                q.append(quantile[i])    
            graph_data.append(q)

        p = pd.DataFrame(graph_data, index=range(10, 100, 10), columns=[[f[1] for f in files]])
        p.plot.bar(title=f"{output} - {type} - {op}")
        print(f"\t saving {output}-{type}-{op}.png")
        pl.savefig(f"{output}-{type}-{op}.png")
