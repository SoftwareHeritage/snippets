#!/usr/bin/env python3

# SPDX-FileCopyrightText: © 2025 Stefano Zacchiroli <zack@upsilon.cc>
# SPDX-License-Identifier: GPL-3.0-or-later
# Last-modified: <2025-09-21 Sun>

# Dependencies (PyPI packages): click, grpcio, swh.graph

import click
import functools
import logging
import grpc
import sys

import swh.graph.grpc.swhgraph_pb2 as swhgraph
import swh.graph.grpc.swhgraph_pb2_grpc as swhgraph_grpc

from google.protobuf.field_mask_pb2 import FieldMask


GRAPH_GRPC_SERVER = "swh1.enst.fr:50091"
ORIGIN_CACHE_SIZE = 1_000_000


@functools.lru_cache(maxsize=ORIGIN_CACHE_SIZE)
def resolve_origin(stub, ori_swhid):
    response = stub.GetNode(swhgraph.GetNodeRequest(swhid=ori_swhid))
    return response.ori.url


def whereis(stub, swhid):
    response = stub.FindPathTo(
        swhgraph.FindPathToRequest(
            src=[swhid],
            target=swhgraph.NodeFilter(types="ori"),
            direction=swhgraph.GraphDirection.BACKWARD,
            mask=FieldMask(paths=["node.swhid"]),
        )
    )
    *_, ori = response.node  # last node in the path is the target, i.e., origin
    return resolve_origin(stub, ori.swhid)


@click.command()
@click.argument("swhid", nargs=-1)
def main(swhid):
    """Find the origin of Software Heritage archive object(s).

    One or more objects should be given as input, specified as SWHIDs (Software Hash
    Identifiers, ISO/IEC 18670).  SWHIDs can be specified as command line arguments. If
    not specified on the command line, SWHIDs will be read from standard input, one per
    line.

    Output is returned on standard output, as a tab-separated file (TSV) with two
    columns: <OBJECT, ORIGIN>, where OBJECT is an input SWHID and ORIGIN the URL of one
    (arbitrary) origin known to Software Heritage for having hosted the object.  In case
    no match is found for an object, an error message will be logged to standard error,
    and no output record emitted (for that object).

    Example:

    \b
    $ swh-graph-grpc-whereis.py swh:1:dir:977fc4b98c0e85816348cebd3b12026407c368b6
    object	origin
    swh:1:dir:977fc4b98c0e85816348cebd3b12026407c368b6	https://github.com/python/cpython

    """

    # Iterate on CLI arguments, if given; on stdin lines otherwise.
    if swhid:
        swhids = iter(swhid)
    else:
        swhids = map(lambda s: s.rstrip(), sys.stdin)

    with grpc.insecure_channel(GRAPH_GRPC_SERVER) as channel:
        stub = swhgraph_grpc.TraversalServiceStub(channel)
        print("object\torigin")
        for swhid in swhids:
            try:
                ori_swhid = whereis(stub, swhid)
                print(f"{swhid}\t{ori_swhid}")
            except grpc._channel._InactiveRpcError:
                logging.error("Cannot find the origin of SWHID %s", swhid)
                continue


if __name__ == "__main__":
    main()
