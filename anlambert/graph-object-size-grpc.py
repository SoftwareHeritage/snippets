#!/usr/bin/env python3

# Copyright (C) 2025  The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information

import time

import click
import grpc
import humanize

import swh.graph.grpc.swhgraph_pb2 as swhgraph
import swh.graph.grpc.swhgraph_pb2_grpc as swhgraph_grpc

GRAPH_GRPC_SERVER = "maxxi.internal.softwareheritage.org:50091"


@click.command()
@click.option(
    "--swh-graph-grpc-server",
    "-g",
    default=GRAPH_GRPC_SERVER,
    show_default=True,
    help="URL of swh-graph GRPC server",
    required=True,
)
@click.option(
    "--max-message-length",
    "-l",
    default=1024 * 1024 * 1024,
    show_default=True,
    help="Maximum length of GRPC messages",
    required=True,
)
@click.argument("swhid", nargs=1, required=True)
def run(swh_graph_grpc_server, max_message_length, swhid):
    """Compute a set of metrics for the SWHID passed as parameter by
    performing a BFS from the associated node in the SWH graph using the GRPC API:

    - number of induced subgraph nodes

    - total number of content objects

    - total number of skipped contents

    - total content objects size in bytes"""
    nb_subgraph_nodes = 0
    nb_contents = 0
    nb_skipped_contents = 0
    total_contents_size = 0

    with grpc.insecure_channel(
        swh_graph_grpc_server,
        options=[
            ("grpc.max_message_length", max_message_length),
            ("grpc.max_send_message_length", max_message_length),
            ("grpc.max_receive_message_length", max_message_length),
        ],
    ) as channel:
        start = time.perf_counter()
        stub = swhgraph_grpc.TraversalServiceStub(channel)
        response = stub.Traverse(swhgraph.TraversalRequest(src=[swhid]))
        for item in response:
            nb_subgraph_nodes += 1
            if item.swhid.startswith("swh:1:cnt:"):
                if not item.cnt.is_skipped:
                    nb_contents += 1
                    total_contents_size += item.cnt.length
                else:
                    nb_skipped_contents += 1
        end = time.perf_counter()

        elapsed_time = humanize.naturaldelta(end - start, minimum_unit="microseconds")
        print(f"BFS execution time = {elapsed_time}")
        print(f"number of subgraph nodes: {nb_subgraph_nodes}")
        print(f"number of contents: {nb_contents}")
        print(f"number of skipped contents: {nb_skipped_contents}")
        total_size = humanize.naturalsize(total_contents_size, binary=True)
        print(f"total contents size in bytes: {total_size}")


if __name__ == "__main__":
    run()
