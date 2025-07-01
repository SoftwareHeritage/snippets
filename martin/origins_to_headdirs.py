#!/usr/bin/env -S python -u
"""
requires: click, swh.graph.grpc

invoke without arguments for further help

set the env variable GRAPH_GRPC_SERVER to the graph's URL, defaults to localhost:50091
"""
from datetime import datetime
from os import environ
from pathlib import Path

import click
import grpc

import swh.graph.grpc.swhgraph_pb2 as swhgraph
import swh.graph.grpc.swhgraph_pb2_grpc as swhgraph_grpc
from swh.model.swhids import CoreSWHID, ObjectType

GRAPH_GRPC_SERVER = environ.get("GRAPH_GRPC_SERVER")
if GRAPH_GRPC_SERVER is None:
    GRAPH_GRPC_SERVER = "localhost:50091"

def traverse(stub, ori:str) -> CoreSWHID:
    """
    Given a gRPC stub to swh-graph, and an origin SWHID, returns the directory SWHID
    of the root of the release having the maximum name (that might be the latest
    version, hopefully)
    """
    response = stub.Traverse(swhgraph.TraversalRequest(
        src=[ori],
        edges="ori:snp,snp:rel,rel:rev,rev:dir",
        return_nodes=swhgraph.NodeFilter(types="rel,rev"),
    ))
    max_rel = ""
    max_rel_rev = None
    for item in response:
        if item.rel and (relname := item.rel.name.decode()) > max_rel and item.successor:
            swhid = CoreSWHID.from_string(item.successor[0].swhid)
            if swhid.object_type == ObjectType.REVISION:
                max_rel = relname
                max_rel_rev = item.successor[0].swhid
        elif item.rev and item.swhid == max_rel_rev and item.successor:
            swhid = CoreSWHID.from_string(item.successor[0].swhid)
            if swhid.object_type == ObjectType.DIRECTORY:
                return swhid
    return None


def traverse_planB(stub, ori:str) -> CoreSWHID:
    """
    like `traverse`, but when there's no release we fallback to sorting revisions by
    name.
    """
    response = stub.Traverse(swhgraph.TraversalRequest(
        src=[ori],
        edges="ori:snp,snp:rev,rev:dir",
        return_nodes=swhgraph.NodeFilter(types="snp,rev"),
    ))
    max_name = ""
    max_name_rev = None
    for item in response:
        if (swhid := CoreSWHID.from_string(item.swhid)).object_type == ObjectType.SNAPSHOT:
            for s in item.successor:
                for l in s.label:
                    if (name := l.name.decode()) > max_name:
                        max_name = name
                        max_name_rev = s.swhid
        elif item.rev and item.swhid == max_name_rev:
            swhid = CoreSWHID.from_string(item.successor[0].swhid)
            if swhid.object_type == ObjectType.DIRECTORY:
                return swhid
    return None



@click.command()
@click.argument("origins_files", type=Path)
@click.argument("dirlist_output")
def main(origins_files:Path, dirlist_output:str):
    """
    From an origin's text file, traverses a graph (via the gRPC server) to find each
    root directories@latest release. The heuristic is that the latest release is the
    one with the maximum name.

    input file should be text: one origin per line, each line should start with the
    origin ID

    output will be a binary file that concatenates each directory ID
    """
    output = open(dirlist_output, 'wb')
    lines_read = 0
    dir_written = 0

    source = open(origins_files)
    with grpc.insecure_channel(GRAPH_GRPC_SERVER, [
        # advanced options from https://github.com/grpc/grpc/blob/master/include/grpc/impl/channel_arg_names.h
        ("grpc.max_receive_message_length", -1),
    ]) as channel:
        stub = swhgraph_grpc.TraversalServiceStub(channel)
        for l in source.readlines():
            ori = f"swh:1:ori:{l[0:40]}"
            lines_read += 1
            try:
                dir_id = traverse(stub, ori)
                if dir_id is None:
                    dir_id = traverse_planB(stub, ori)
                    if dir_id is None:
                        raise ValueError("not found !")
                output.write(dir_id.object_id)
                dir_written += 1
            except Exception as e:
                print(f"while traversing {l.strip()}: {e}")
                # raise e
            if lines_read % 100 == 0:
                print(datetime.now().isoformat(), f"traversed {lines_read} origins, found {dir_written}")

    source.close()
    output.close()
    print(f"Done. From {lines_read} origins, found {dir_written} directories. IDs concatenated to {dirlist_output}")

if __name__ == "__main__":
    main()
