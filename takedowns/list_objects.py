# Copyright (C) 2021  The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information

import datetime
import functools
import hashlib
import logging
import os
import pickle
import sys
from typing import Callable, Collection, Dict, Iterator, List, Optional, Tuple, Union

from igraph import Graph as _Graph
from igraph import Vertex, plot, summary
from requests import Session

from swh.model.model import Revision, TargetType
from swh.model.swhids import ExtendedObjectType as ObjectType
from swh.model.swhids import ExtendedSWHID as SWHID
from swh.storage import get_storage
from swh.storage.algos.origin import iter_origin_visit_statuses, iter_origin_visits
from swh.storage.algos.snapshot import snapshot_get_all_branches
from swh.storage.interface import StorageInterface

logger = logging.getLogger(__name__)


@functools.lru_cache(32)
def object_type(tt: Union[str, TargetType]) -> ObjectType:
    value: Optional[str] = None
    if tt == "file":
        return ObjectType.CONTENT
    elif isinstance(tt, str):
        value = tt
        name = tt
    else:
        name = tt.name

    if value is not None:
        try:
            return ObjectType(value)
        except ValueError:
            pass
    return ObjectType[name]


class Graph(_Graph):
    """A graph, backed by igraph, with uniquely named vertices"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._vertices: Dict[str, int] = {}

    def add_vertex(self, name, *args, **kwargs):
        try:
            return self.vs[self._vertices[name]]
        except (KeyError, IndexError):
            ret = super().add_vertex(name, *args, **kwargs)
            self._vertices[name] = ret.index
            return ret


def add_node_to_graph(graph: Graph, swhid: SWHID) -> Tuple[Vertex, bool]:
    """Add the given `swhid` as a new vertex in the `graph`.

    Arguments:
      - graph: the graph on which to do the processing
      - swhid: the new object to add to the graph

    Returns:
      - the new Vertex for the given `swhid` (on which one can set attributes after processing, if needed)
      - a boolean whether the vertex was created or not

    """
    node_name = str(swhid)
    created = node_name not in graph._vertices
    vertex = graph.add_vertex(
        node_name, swhid=swhid, fetched=swhid.object_type == ObjectType.CONTENT
    )

    return vertex, created


def init_graph(swhids: List[SWHID], pickle_filename: str) -> Graph:
    """Initialize the Graph structure, either from a pickled object, or from a single given swhid.

    Arguments:
      - swhid: the primary anchor swhid for the graph in question
      - pickle_filename: a the filename to a pickle file that we'd load to initialize
        the graph

    """
    if os.path.exists(pickle_filename):
        try:
            ret = pickle.load(open(pickle_filename, "rb"))
            if not isinstance(ret, Graph):
                raise TypeError("Unknown pickle data")
            logger.debug("Known nodes: %s", len(ret._vertices))
            return ret
        except Exception:
            logger.exception("Could not load pickle file, fallback to basic graph")

    # Initialize the graph with the given swhids
    ret = Graph(directed=True)
    for swhid in swhids:
        add_node_to_graph(ret, swhid)
    return ret


def populate_subtrees(
    graph: Graph,
    storage: StorageInterface,
    graph_baseurl: Optional[str] = None,
):
    """Populate the graph data structure with the subtrees of all the swhids already
    contained in the graph.

    Arguments:
      - swhids: the set of root swhids to process
      - storage: the instance of swh.storage on which to search the swhids and their outbound edges.
      - graph_baseurl: the base URL of an instance of swh.graph
    """
    if "fetched" not in graph.vs.attribute_names():
        logger.info("Outbound edges already fetched")
        return

    session = Session()

    iteration = 0
    while True:
        iteration += 1
        vertices = graph.vs.select(fetched_eq=False)
        logger.debug(
            "Iteration %s: %s nodes to fetch (%s known)",
            iteration,
            len(vertices),
            len(graph.vs),
        )
        if not vertices:
            break
        for i, vertex in enumerate(vertices):
            if vertex["fetched"]:
                continue
            add_outbound_edges_to_graph(
                graph, vertex["swhid"], storage, graph_baseurl, session
            )
            vertex["fetched"] = True
            if (i + 1) % 100 == 0:
                logger.debug(
                    "Iteration %s: fetched %s nodes (%s known)",
                    iteration,
                    i + 1,
                    len(graph.vs),
                )

    del graph.vs["fetched"]

    return graph


def outbound_edges_from_swh_graph(
    graph: Graph,
    swhid: SWHID,
    graph_baseurl: str,
    session: Optional[Session] = None,
):
    """Get the subtree of objects referenced by a given one, from swh.graph (based at `graph_baseurl`).

    Returns `True` if the list of outbound edges found is (expected to be) exhaustive.
    """
    if not session:
        session = Session()

    edges_url = f"{graph_baseurl.rstrip('/')}/graph/visit/edges/{swhid}"

    response = session.get(edges_url, stream=True)
    if response.status_code in (400, 404):
        logger.debug("Object %s not found in swh.graph", swhid)
        return False

    response.raise_for_status()

    logger.debug("Processing outbound edges of %s from swh.graph...", swhid)

    new_nodes = 0
    known_nodes: Dict[str, Tuple[int, bool]] = {}

    def add_vertex(name: str):
        nonlocal new_nodes

        swhid = SWHID.from_string(name)
        vertex, created = add_node_to_graph(graph, swhid)
        if created and swhid.object_type != ObjectType.ORIGIN:
            vertex["fetched"] = True
        new_nodes += created
        known_nodes[name] = vertex.index, created

    def add_edges():
        for node in node_batch:
            if node not in known_nodes:
                add_vertex(node)

        edges_to_add = []
        for left, right in edge_batch:
            left_id, created = known_nodes[left]
            if not created:
                continue
            right_id, _ = known_nodes[right]
            edges_to_add.append((left_id, right_id))

        graph.add_edges(edges_to_add)

        edge_batch[:] = []
        node_batch.clear()

    edge_batch = []
    node_batch = set()

    edges = 0
    for line in response.iter_lines():
        edges += 1
        left, right = line.decode().strip().split()
        if left not in node_batch and left not in known_nodes:
            node_batch.add(left)
        if right not in node_batch and right not in known_nodes:
            node_batch.add(right)
        edge_batch.append((left, right))

        if edges % 1000 == 0:
            logger.debug("Read %s edges (%s nodes added so far)", edges, new_nodes)

        if len(edge_batch) >= 1000000 or len(node_batch) >= 100000:
            logger.debug(
                "Registering %s new edges (%s new nodes)...",
                len(edge_batch),
                len(node_batch),
            )
            add_edges()

    add_edges()

    logger.info(
        "Found %s new nodes from %s in swh.graph",
        new_nodes,
        swhid,
    )

    return swhid.object_type != ObjectType.ORIGIN


def content_outbound_edges_from_storage(
    storage: StorageInterface,
    swhid: SWHID,
):
    return


def directory_outbound_edges_from_storage(
    storage: StorageInterface, swhid: SWHID
) -> Iterator[Tuple[SWHID, SWHID]]:
    for entry in storage.directory_ls(swhid.object_id):
        succ_type = object_type(entry["type"])
        succ_swhid = SWHID(object_type=succ_type, object_id=entry["target"])
        if succ_type == ObjectType.REVISION:
            logger.info("Ignored submodule edge %s -> %s", swhid, succ_swhid)
            continue
        yield (swhid, succ_swhid)


def revision_outbound_edges_from_storage(
    storage: StorageInterface,
    swhid: SWHID,
) -> Iterator[Tuple[SWHID, SWHID]]:
    for rev_d in storage.revision_log([swhid.object_id], limit=100):
        rev = Revision.from_dict(rev_d)
        rev_swhid = rev.swhid().to_extended()

        dir_swhid = SWHID(object_type=ObjectType.DIRECTORY, object_id=rev.directory)
        yield (rev_swhid, dir_swhid)

        for succ_rev in rev.parents:
            succ_swhid = SWHID(object_type=ObjectType.REVISION, object_id=succ_rev)
            yield (rev_swhid, succ_swhid)


def release_outbound_edges_from_storage(
    storage: StorageInterface, swhid: SWHID
) -> Iterator[Tuple[SWHID, SWHID]]:
    [rel] = storage.release_get([swhid.object_id])
    if not rel:
        logger.warning("Release %s not found", swhid)
        return
    assert rel.target
    target_swhid = SWHID(object_id=rel.target, object_type=object_type(rel.target_type))
    yield (swhid, target_swhid)


def snapshot_outbound_edges_from_storage(
    storage: StorageInterface, swhid: SWHID
) -> Iterator[Tuple[SWHID, SWHID]]:
    snp = snapshot_get_all_branches(storage, swhid.object_id)
    if not snp:
        logger.warning("Snapshot %s not found", swhid)
        return

    for branch in snp.branches.values():
        if branch is None or branch.target_type.value == "alias":
            continue
        target_swhid = SWHID(
            object_id=branch.target, object_type=object_type(branch.target_type)
        )
        yield (swhid, target_swhid)


def origin_outbound_edges_from_storage(
    storage: StorageInterface,
    swhid: SWHID,
) -> Iterator[Tuple[SWHID, SWHID]]:
    [origin] = storage.origin_get_by_sha1([swhid.object_id])
    if not origin:
        logger.warning("Origin %s not found", swhid)
        return

    for visit in iter_origin_visits(storage, origin["url"]):
        assert visit.visit
        for status in iter_origin_visit_statuses(storage, visit.origin, visit.visit):
            if status.snapshot:
                snapshot_swhid = SWHID(
                    object_id=status.snapshot, object_type=ObjectType.SNAPSHOT
                )
                yield (swhid, snapshot_swhid)


outbound_edges_from_storage_map: Dict[
    ObjectType,
    Callable[[StorageInterface, SWHID], Iterator[Tuple[SWHID, SWHID]]],
] = {
    ObjectType.CONTENT: content_outbound_edges_from_storage,
    ObjectType.DIRECTORY: directory_outbound_edges_from_storage,
    ObjectType.REVISION: revision_outbound_edges_from_storage,
    ObjectType.RELEASE: release_outbound_edges_from_storage,
    ObjectType.SNAPSHOT: snapshot_outbound_edges_from_storage,
    ObjectType.ORIGIN: origin_outbound_edges_from_storage,
}


def add_outbound_edges_to_graph(
    graph: Graph,
    swhid: SWHID,
    storage: StorageInterface,
    graph_baseurl: Optional[str] = None,
    session: Optional[Session] = None,
):
    obj_type = swhid.object_type

    if graph_baseurl:
        all_found = outbound_edges_from_swh_graph(graph, swhid, graph_baseurl, session)
        if all_found:
            return
        else:
            logger.debug("Getting other outbound edges of %s from swh.storage", swhid)

    outbound_edges_from_storage_fn = outbound_edges_from_storage_map.get(obj_type)
    if outbound_edges_from_storage_fn:
        new_edges = []
        for left, right in outbound_edges_from_storage_fn(storage, swhid):
            left_vertex, created = add_node_to_graph(graph, left)
            if left_vertex["fetched"]:
                continue
            right_vertex, created = add_node_to_graph(graph, right)
            new_edges.append((left_vertex.index, right_vertex.index))

        graph.add_edges(new_edges)

        for index in set(left for left, _ in new_edges):
            graph.vs[index]["fetched"] = True

    else:
        raise ValueError("Unknown object type: %s" % obj_type)


def record_inbound_edges_outside_graph(
    graph: Graph,
    storage: StorageInterface,
    graph_baseurl: Optional[str] = None,
    session: Optional[Session] = None,
):
    """Check if objects have inbound edges outside the subgraph"""
    if graph_baseurl and session is None:
        session = Session()

    if "inbound_edges_checked" not in graph.vs.attribute_names():
        graph.vs["inbound_edges_checked"] = False

    if "has_inbound_edges_outside_subgraph" not in graph.vs.attribute_names():
        graph.vs["has_inbound_edges_outside_subgraph"] = False

    total_nodes = len(graph.vs)
    inbound_unknown = len(graph.vs.select(inbound_edges_checked=False))
    logger.info(
        "Total nodes: %s, inbound nodes unknown: %s", total_nodes, inbound_unknown
    )

    for count, vid in enumerate(graph.topological_sorting()):
        vertex = graph.vs[vid]
        swhid = vertex["swhid"]

        if count == 0 or count + 1 == total_nodes or count % 100 == 99:
            logger.info("Checking inbound edges for node %s/%s", count + 1, total_nodes)

        if vertex["inbound_edges_checked"]:
            continue

        if swhid.object_type == ObjectType.ORIGIN:
            vertex["inbound_edges_checked"] = True
            continue

        for pred in vertex.predecessors():
            if not pred["inbound_edges_checked"]:
                logger.warning(
                    "record_inbound_edges_outside_graph %s: predecessor %s has not been checked yet!",
                    swhid,
                    pred["swhid"],
                )
                raise ValueError("toposort broken!")

        if any(
            pred["has_inbound_edges_outside_subgraph"] for pred in vertex.predecessors()
        ):
            vertex["has_inbound_edges_outside_subgraph"] = True
            vertex["inbound_edges_checked"] = True
            continue

        predecessors = {pred["swhid"] for pred in vertex.predecessors()}

        result = find_one_inbound_edge(
            swhid, predecessors, storage, graph_baseurl, session
        )
        if result:
            found, reason = result
            logger.debug("Found inbound edge for %s using %s: %s", swhid, reason, found)
            vertex["has_inbound_edges_outside_subgraph"] = True
            vertex["inbound_edge_outside_subgraph"] = found

        vertex["inbound_edges_checked"] = True


def find_one_inbound_edge(
    swhid: SWHID,
    known_predecessors: Collection[SWHID],
    storage: StorageInterface,
    graph_baseurl: Optional[str] = None,
    session: Optional[Session] = None,
) -> Optional[Tuple[SWHID, str]]:
    """Find one inbound edge for `swhid` outside of `known_predecessors`.

    Arguments:
      swhid: the object for which we should look for inbound edges
      known_predecessors: known objects that we should ignore as predecessors for `swhid`
      storage: the storage to check against
      graph_baseurl: the url of the swh.graph API to query against
      session: a common requests session for swh.graph API calls

    Returns:
      a couple with the `swhid` for a predecessor that was not previously known, and the way it was found
    """

    if graph_baseurl:
        found = get_one_inbound_edge_swh_graph(
            graph_baseurl, swhid, known_predecessors, session=session
        )
        if found:
            return found, "swh.graph"

    found = get_one_inbound_edge_storage(storage, swhid, known_predecessors)
    if found:
        return found, "swh.storage:find_recent_references"

    return None


def get_one_inbound_edge_swh_graph(
    graph_baseurl: str,
    swhid: SWHID,
    known_predecessors: Collection[SWHID],
    session: Optional[Session] = None,
) -> Optional[SWHID]:
    if not session:
        session = Session()

    nodes_url = f"{graph_baseurl.rstrip('/')}/graph/neighbors/{swhid}"
    params = {
        "direction": "backward",
        "max_matching_nodes": str(len(known_predecessors) + 1),
    }

    response = session.get(nodes_url, params=params, stream=True)

    if response.status_code in (404, 400):
        return None

    response.raise_for_status()

    found: Optional[SWHID] = None
    s_swhid = str(swhid)
    s_pred = {str(p_swhid) for p_swhid in known_predecessors}
    for node in response.iter_lines(decode_unicode=True):
        node = node.strip()
        if not node or found or node == s_swhid:
            continue
        if node not in s_pred:
            found = SWHID.from_string(node)

    return found


def get_one_inbound_edge_storage(
    storage: StorageInterface,
    swhid: SWHID,
    known_predecessors: Collection[SWHID],
) -> Optional[SWHID]:
    limit = len(known_predecessors) + 1
    references = storage.object_find_recent_references(swhid, limit=limit)

    if not references:
        return None

    while len(set(references)) != len(references) and len(references) == limit:
        limit = 2 * limit
        references = storage.object_find_recent_references(swhid, limit=limit)

    outside = set(references) - set(known_predecessors)
    return next(iter(outside)) if outside else None


def plot_graph(graph: Graph):
    color_dict = {
        ObjectType.CONTENT: "pink",
        ObjectType.DIRECTORY: "lavender",
        ObjectType.REVISION: "orchid",
        ObjectType.RELEASE: "olive",
        ObjectType.SNAPSHOT: "aqua",
        ObjectType.ORIGIN: "khaki",
    }
    graph.vs["label"] = [swhid.object_id.hex()[:8] for swhid in graph.vs["swhid"]]
    plot(
        graph,
        "%s.svg" % graph.vs[0]["swhid"],
        layout=graph.layout_sugiyama(),
        vertex_color=[
            color_dict.get(swhid.object_type, "red") for swhid in graph.vs["swhid"]
        ],
        bbox=(10000, 100000),
    )
    del graph.vs["label"]


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(name)-12s %(levelname)-8s %(message)s"
    )
    logger.setLevel(logging.DEBUG)
    graph: Optional[Graph] = None
    try:
        storage = get_storage(
            cls="postgresql", db="service=swh", objstorage={"cls": "memory"}
        )

        swhids = []
        for arg in sys.argv[1:]:
            if arg.startswith("swh:1:"):
                swhid = SWHID.from_string(arg)
            else:
                sha1 = hashlib.sha1(arg.encode()).hexdigest()
                swhid = SWHID.from_string(f"swh:1:ori:{sha1}")
                logger.info(
                    "Assuming %s is an origin URL; computed origin swhid: %s",
                    arg,
                    swhid,
                )

            swhids.append(swhid)

        swhid = swhids[0]

        graph_baseurl = "http://granet.internal.softwareheritage.org:5009/"
        graph = init_graph(swhids, pickle_filename=f"{swhid}.pickle")

        populate_subtrees(
            graph,
            storage,
            graph_baseurl,
        )

        record_inbound_edges_outside_graph(graph, storage, graph_baseurl)
    finally:
        if graph:
            date = datetime.datetime.now().strftime("%Y%m%dT%H%M%S")
            pickle_name = f"{swhid}.{date}.pickle"
            logger.info("Dumping to %s", pickle_name)
            graph.write_pickle(pickle_name)
            # plot_graph(graph)
            summary(graph)
            logger.info(
                "Nodes with external inbound edges found: %s",
                len(graph.vs.select(has_inbound_edges_outside_subgraph_eq=True)),
            )
            logger.info(
                "Nodes with no external inbound edges found: %s",
                len(graph.vs.select(has_inbound_edges_outside_subgraph_eq=False)),
            )
