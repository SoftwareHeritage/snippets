# Copyright (C) 2021  The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information

import pickle
import sys

import yaml

from list_objects import Graph

if __name__ == "__main__":
    graph = pickle.load(open(sys.argv[1], "rb"))

    nodes_to_remove = [
        str(s) for s in graph.vs.select(has_inbound_edges_outside_subgraph_eq=False)["swhid"]
    ]
    nodes_to_keep = [
        str(s) for s in graph.vs.select(has_inbound_edges_outside_subgraph_eq=True)["swhid"]
    ]

    yaml.dump(
        {
            "version": 1,
            "request": {"date": None, "object": None,},
            "decision": {"date": None, "action": None,},
            "affected_nodes": {
                "kept": sorted(nodes_to_keep),
                "removed": sorted(nodes_to_remove),
            },
        },
        sys.stdout,
    )
