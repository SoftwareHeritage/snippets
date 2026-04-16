import datetime

import matplotlib.pyplot as plt
import requests
from tqdm import tqdm

MARKERS = ["x", ".", "v", "^", "d", "*"]

# Copy-pasted from https://docs.softwareheritage.org/devel/swh-export/graph/dataset.html#summary-of-dataset-versions to a spreadsheet then from the spreadsheet to here
s = """
2026-03-02  57268096450 1072900078798
2025-10-08	53529848761	1003518287197
2025-05-18	49903891086	905462853965
2024-12-06	44573066306	769494968843
2024-08-23	41074031225	644153760912
2024-05-16	38977225252	604179689399
2023-09-06	34121566250	517399308984
2022-12-07	27397574122	416565871870
2022-04-25	25340003875	375867687011
2021-03-23	20667308808	232748148441
2020-12-15	19330739526	213848749638
2020-05-20	17075708289	203351589619
2019-01-28	11683687950	159578271511
"""

lines = [line.split() for line in reversed(s.split("\n")) if line]

nodes = [(date, int(num_nodes)) for (date, num_nodes, _) in lines]
arcs = [(date, int(num_arcs)) for (date, _, num_arcs) in lines]

dates = [datetime.date.fromisoformat(line[0]) for line in lines]
nodes = [int(line[1]) for line in lines]
arcs = [int(line[2]) for line in lines]

fig, axs = plt.subplots(3, 4, figsize=(20, 15))
axs[0, 0].plot(dates, nodes, marker="x")
axs[0, 0].set_title("Nodes")

nodes_by_type = []
node_types = set()
for date in tqdm(dates, desc="graph.nodes.stats.txt"):
    url = f"https://softwareheritage.s3.us-east-1.amazonaws.com/graph/{date}/compressed/graph.nodes.stats.txt"
    r = requests.get(url)
    d = {}
    if r.status_code == 200:
        file = r.text
        for line in file.split("\n"):
            if line:
                (k, v) = line.split()
                d[k] = int(v)
                node_types.add(k)
    nodes_by_type.append(d)
node_types = list(sorted(node_types))

for marker, node_type in zip(MARKERS, node_types):
    axs[1, 0].plot(
        dates, [d.get(node_type) for d in nodes_by_type], label=node_type, marker=marker
    )
axs[1, 0].set_title("Nodes (by type)")
axs[1, 0].legend(loc="upper left", frameon=False)

for marker, node_type in zip(MARKERS, node_types):
    axs[2, 0].plot(
        dates, [d.get(node_type) for d in nodes_by_type], label=node_type, marker=marker
    )
axs[2, 0].set_title("Nodes (by type)")
axs[2, 0].legend(loc="upper left", frameon=False)
axs[2, 0].set_yscale('log')

axs[0, 1].plot(dates, arcs, marker="x")
axs[0, 1].set_title("Arcs (total)")

ax = axs[1, 2]
keys = set()
arcs_by_type = []
for date in tqdm(dates, desc="graph.edges.stats.txt"):
    url = f"https://softwareheritage.s3.us-east-1.amazonaws.com/graph/{date}/compressed/graph.edges.stats.txt"
    r = requests.get(url)
    d = {}
    if r.status_code == 200:
        file = r.text
        for line in file.split("\n"):
            if line:
                (k, v) = line.split()
                (src, dst) = k.split(":")
                d[src] = d.get(src, 0) + int(v)
                keys.add(k)
    arcs_by_type.append(d)

for marker, node_type in zip(MARKERS, node_types):
    axs[1, 1].plot(
        dates, [d.get(node_type) for d in arcs_by_type], label=node_type, marker=marker
    )
axs[1, 1].set_title("Arcs (by source node type)")
axs[1, 1].legend(loc="upper left", frameon=False)

for marker, node_type in zip(MARKERS, node_types):
    axs[2, 1].plot(
        dates, [d.get(node_type) for d in arcs_by_type], label=node_type, marker=marker
    )
axs[2, 1].set_title("Arcs (by source node type)")
axs[2, 1].legend(loc="upper left", frameon=False)
axs[2, 1].set_yscale('log')

axs[0, 2].plot(
    dates,
    [num_arcs / num_nodes for (num_arcs, num_nodes) in zip(arcs, nodes)],
    marker="x",
)
axs[0, 2].set_title("Arcs per node / avg outdegree")

for marker, node_type in zip(MARKERS, node_types):
    axs[1, 2].plot(
        dates,
        [
            da.get(node_type, 0) / dn.get(node_type) if dn else None
            for (da, dn) in zip(arcs_by_type, nodes_by_type)
        ],
        label=node_type,
        marker=marker,
    )
axs[1, 2].set_title("Avg outdegree (by node type)")
axs[1, 2].legend(loc="upper left", frameon=False)

forward_graph_bytes = []
for date in tqdm(dates, desc="graph.graph"):
    url = f"https://softwareheritage.s3.us-east-1.amazonaws.com/graph/{date}/compressed/graph.graph"
    r = requests.head(url)
    if r.status_code == 200:
        forward_graph_bytes.append(int(r.headers["Content-Length"]) / 1_000_000_000)
    else:
        forward_graph_bytes.append(None)
backward_graph_bytes = []
for date in tqdm(dates, desc="graph-transposed.graph"):
    url = f"https://softwareheritage.s3.us-east-1.amazonaws.com/graph/{date}/compressed/graph-transposed.graph"
    r = requests.head(url)
    if r.status_code == 200:
        backward_graph_bytes.append(int(r.headers["Content-Length"]) / 1_000_000_000)
    else:
        backward_graph_bytes.append(None)

fix_compflag_date = datetime.date.fromisoformat("2025-10-07")
axs[0, 3].plot(  # 290GB on 2025-10-08 before I fixed the compflags
    [*dates[0:-2], fix_compflag_date, *dates[-2:]],
    [*forward_graph_bytes[0:-2], 290, *forward_graph_bytes[-2:]],
    label="forward",
    marker="x",
)
axs[0, 3].plot(  # 195GB on 2025-10-08 before I fixed the compflags
    [*dates[0:-2], fix_compflag_date, *dates[-2:]],
    [*backward_graph_bytes[0:-2], 195, *backward_graph_bytes[-2:]],
    label="backward",
    marker=".",
)
axs[0, 3].set_title("File size (GB)")
axs[0, 3].legend(loc="upper left", frameon=False)
axs[0, 3].annotate(
    "bad compflags",
    xy=(fix_compflag_date, 290),
    xytext=(fix_compflag_date + datetime.timedelta(days=300), 320),
    arrowprops=dict(facecolor="black", shrink=0.05),
)
axs[0, 3].annotate(
    "bad compflags",
    xy=(fix_compflag_date, 195),
    xytext=(fix_compflag_date + datetime.timedelta(days=300), 320),
    arrowprops=dict(facecolor="black", shrink=0.05),
)

axs[1, 3].plot(
    dates,
    [
        num_bytes * 1_000_000_000 * 8.0 / num_arcs if num_bytes else None
        for (num_bytes, num_arcs) in zip(forward_graph_bytes, arcs)
    ],
    label="forward",
    marker="x",
)
axs[1, 3].plot(
    dates,
    [
        num_bytes * 1_000_000_000 * 8.0 / num_arcs if num_bytes else None
        for (num_bytes, num_arcs) in zip(backward_graph_bytes, arcs)
    ],
    label="backward",
    marker=".",
)
axs[1, 3].set_title("Bits per arc")
axs[1, 3].legend(loc="upper right", frameon=False)

fig.savefig("plot.png")
