# Copyright (C) 2021  The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information

import datetime
import functools
import logging
import os
import pickle
import sys
from typing import (Callable, Collection, Dict, Iterable, Iterator, Optional,
                    Tuple, Union)

from igraph import Graph as _Graph
from igraph import Vertex, plot, summary
from requests import Session
from swh.model.identifiers import ExtendedObjectType as ObjectType
from swh.model.identifiers import ExtendedSWHID as SWHID
from swh.model.model import Revision, TargetType
from swh.storage import get_storage
from swh.storage.algos.origin import (iter_origin_visit_statuses,
                                      iter_origin_visits)
from swh.storage.algos.snapshot import snapshot_get_all_branches
from swh.storage.interface import StorageInterface
from swh.storage.postgresql.storage import Storage as PgStorage

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


def init_graph(swhid: SWHID, pickle_filename: str) -> Graph:

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
    add_node_to_graph(ret, swhid)
    return ret


def get_descendents_graph(
    graph: Graph,
    storage: StorageInterface,
    graph_baseurl: Optional[str] = None,
):
    """Get a graph containing all descendents of the set of `swhids`.

    Arguments:
      - swhids: the set of root swhids to process
      - storage: the instance of swh.storage on which to search the swhids and their descendents.
      - graph_baseurl: the base URL of an instance of swh.graph
    """
    if "fetched" not in graph.vs.attribute_names():
        logger.info("Descendents already fetched")
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
            add_descendents_to_graph(
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


def descendents_from_swh_graph(
    graph: Graph,
    swhid: SWHID,
    graph_baseurl: str,
    session: Optional[Session] = None,
):
    """Get the descendents of an object from swh.graph (based at `graph_baseurl`).

    Returns `True` if the list of descendents found is (supposed to be) exhaustive.
    """
    if not session:
        session = Session()

    edges_url = f"{graph_baseurl.rstrip('/')}/graph/visit/edges/{swhid}"

    response = session.get(edges_url, stream=True)
    if response.status_code == 404:
        logger.debug("Object %s not found in swh.graph", swhid)
        return False

    response.raise_for_status()

    logger.debug("Processing descendents of %s from swh.graph...", swhid)

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


def content_descendents_from_storage(
    graph: Graph, swhid: SWHID, storage: StorageInterface
):
    return


def directory_descendents_from_storage(
    graph: Graph, swhid: SWHID, storage: StorageInterface
) -> Iterator[Tuple[SWHID, SWHID]]:
    for entry in storage.directory_ls(swhid.object_id):
        succ_type = object_type(entry["type"])
        succ_swhid = SWHID(object_type=succ_type, object_id=entry["target"])
        if succ_type == ObjectType.REVISION:
            logger.info("Ignored submodule edge %s -> %s", swhid, succ_swhid)
            continue
        yield (swhid, succ_swhid)


def revision_descendents_from_storage(
    graph: Graph, swhid: SWHID, storage: StorageInterface
) -> Iterator[Tuple[SWHID, SWHID]]:
    for rev_d in storage.revision_log([swhid.object_id], limit=100):
        rev = Revision.from_dict(rev_d)
        rev_swhid = rev.swhid().to_extended()

        dir_swhid = SWHID(object_type=ObjectType.DIRECTORY, object_id=rev.directory)
        yield (rev_swhid, dir_swhid)

        for succ_rev in rev.parents:
            succ_swhid = SWHID(object_type=ObjectType.REVISION, object_id=succ_rev)
            yield (rev_swhid, succ_swhid)


def release_descendents_from_storage(
    graph: Graph, swhid: SWHID, storage: StorageInterface
) -> Iterator[Tuple[SWHID, SWHID]]:
    [rel] = storage.release_get([swhid.object_id])
    if not rel:
        logger.warning("Release %s not found", swhid)
        return
    assert rel.target
    target_swhid = SWHID(object_id=rel.target, object_type=object_type(rel.target_type))
    yield (swhid, target_swhid)


def snapshot_descendents_from_storage(
    graph: Graph, swhid: SWHID, storage: StorageInterface
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


def origin_descendents_from_storage(
    graph: Graph, swhid: SWHID, storage: StorageInterface
) -> Iterator[Tuple[SWHID, SWHID]]:
    [origin] = storage.origin_get_by_sha1([swhid.object_id])
    if not origin:
        logger.warning("Origin %s not found", swhid)
        return

    for visit in iter_origin_visits(storage, origin["url"]):
        for status in iter_origin_visit_statuses(storage, visit.origin, visit.visit):
            if status.snapshot:
                snapshot_swhid = SWHID(
                    object_id=status.snapshot, object_type=ObjectType.SNAPSHOT
                )
                yield (swhid, snapshot_swhid)


descendents_from_storage_map: Dict[
    ObjectType,
    Callable[[Graph, SWHID, StorageInterface], Iterator[Tuple[SWHID, SWHID]]],
] = {
    ObjectType.CONTENT: content_descendents_from_storage,
    ObjectType.DIRECTORY: directory_descendents_from_storage,
    ObjectType.REVISION: revision_descendents_from_storage,
    ObjectType.RELEASE: release_descendents_from_storage,
    ObjectType.SNAPSHOT: snapshot_descendents_from_storage,
    ObjectType.ORIGIN: origin_descendents_from_storage,
}


def add_descendents_to_graph(
    graph: Graph,
    swhid: SWHID,
    storage: StorageInterface,
    graph_baseurl: Optional[str] = None,
    session: Optional[Session] = None,
):
    obj_type = swhid.object_type

    if graph_baseurl:
        all_found = descendents_from_swh_graph(graph, swhid, graph_baseurl, session)
        if all_found:
            return
        else:
            logger.debug("Getting other descendents of %s from swh.storage", swhid)

    descendents_from_storage = descendents_from_storage_map.get(obj_type)
    if descendents_from_storage:
        new_edges = []
        for left, right in descendents_from_storage(graph, swhid, storage):
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


def check_predecessors_outside_graph(
    graph: Graph,
    storage: StorageInterface,
    graph_baseurl: Optional[str] = None,
    session: Optional[Session] = None,
):
    if graph_baseurl and session is None:
        session = Session()

    graph.vs["predecessors_outside_subgraph"] = False
    graph.vs["touched"] = False

    for vid in graph.topological_sorting():
        vertex = graph.vs[vid]
        vertex["touched"] = True
        swhid = vertex["swhid"]

        if swhid.object_type == ObjectType.ORIGIN:
            continue

        for pred in vertex.predecessors():
            if not pred["touched"]:
                logger.warning("Processing %s: predecessor %s has not been touched!", swhid, pred["swhid"])
                raise ValueError("toposort broken!")

        if any(pred["predecessors_outside_subgraph"] for pred in vertex.predecessors()):
            vertex["predecessors_outside_subgraph"] = True
            continue

        if graph_baseurl:
            if check_antecedents_swh_graph(vertex, graph_baseurl, session):
                logger.info("Found antecedent for %s in swh.graph", swhid)
                vertex["predecessors_outside_subgraph"] = True
                continue

        predecessors = {pred["swhid"] for pred in vertex.predecessors()}

        if swhid.object_type == ObjectType.SNAPSHOT:
            if check_antecedents_storage_visit(storage, swhid, predecessors):
                logger.info("Found visit with snapshot %s", swhid)
                vertex["predecessors_outside_subgraph"] = True
                continue

        if check_antecedents_storage_snapshot(storage, swhid, predecessors):
            logger.info("Found snapshot containing %s", swhid)
            vertex["predecessors_outside_subgraph"] = True
            continue

        if swhid.object_type != ObjectType.SNAPSHOT:
            if check_antecedents_storage_release(storage, swhid, predecessors):
                logger.info("Found release containing %s", swhid)
                vertex["predecessors_outside_subgraph"] = True
                continue

        if swhid.object_type == ObjectType.REVISION:
            if check_antecedents_storage_revision(storage, swhid, predecessors):
                logger.info("Found revision with %s as parent", swhid)
                vertex["predecessors_outside_subgraph"] = True
                continue

        if swhid.object_type == ObjectType.DIRECTORY:
            if check_antecedents_storage_dir_in_rev(storage, swhid, predecessors):
                logger.info("Found revision with %s as directory", swhid)
                vertex["predecessors_outside_subgraph"] = True
                continue

        if check_antecedents_storage_directory(storage, swhid, predecessors):
            logger.info("Found directory with %s in it", swhid)
            vertex["predecessors_outside_subgraph"] = True
            continue

        logger.info("No predecessors found for %s", swhid)


def check_antecedents_swh_graph(
    vertex: Vertex, graph_baseurl: str, session: Optional[Session] = None
) -> bool:
    if not session:
        session = Session()

    swhid = vertex["swhid"]

    count_url = f"{graph_baseurl.rstrip('/')}/graph/neighbors/count/{swhid}"
    nodes_url = f"{graph_baseurl.rstrip('/')}/graph/neighbors/{swhid}"
    params = {"direction": "backward"}

    count_response = session.get(count_url, params=params)
    if count_response.status_code == 404:
        logger.debug("Object %s not found in swh.graph", swhid)
        return False

    count_response.raise_for_status()
    known_neighbors = int(count_response.content)
    logger.debug(
        "%s has %s predecessors in swh.graph, %s in the current subgraph",
        swhid,
        known_neighbors,
        vertex.indegree(),
    )
    if known_neighbors > vertex.indegree():
        return True

    response = session.get(nodes_url, params=params, stream=True)

    found = False
    s_swhid = str(swhid)
    s_pred = set(str(pred["swhid"]) for pred in vertex.predecessors())
    for node in response.iter_lines(decode_unicode=True):
        if found or node == s_swhid:
            continue
        if node not in s_pred:
            found = True

    return found


def check_antecedents_storage_visit(
    storage: StorageInterface, swhid: SWHID, predecessors: Collection[SWHID]
):
    assert isinstance(storage, PgStorage), "Need to use a `local` storage instance"
    with storage.db() as db:
        with db.transaction() as cur:
            cur.execute("""
              select distinct(digest(origin.url, 'sha1'))
              from origin
              inner join origin_visit_status on origin.id = origin_visit_status.origin
              where snapshot = %s
              limit %s
            """, (swhid.object_id, len(predecessors) + 1))
            results = {SWHID(object_id=line[0], object_type=ObjectType.ORIGIN) for line in cur.fetchall()}

    return bool(results - set(predecessors))

def check_antecedents_storage_snapshot(
    storage: StorageInterface, swhid: SWHID, predecessors: Collection[SWHID]
):
    assert isinstance(storage, PgStorage), "Need to use a `local` storage instance"
    with storage.db() as db:
        with db.transaction() as cur:
            cur.execute("""
              select distinct(snapshot.id)
              from snapshot
              inner join snapshot_branches on snapshot.object_id = snapshot_branches.snapshot_id
              inner join snapshot_branch on snapshot_branches.branch_id = snapshot_branch.object_id
              where snapshot_branch.target = %s and snapshot_branch.target_type = %s
              limit %s
            """, (swhid.object_id, swhid.object_type.name.lower(), len(predecessors) + 1))
            results = {SWHID(object_id=line[0], object_type=ObjectType.SNAPSHOT) for line in cur.fetchall()}

    return bool(results - set(predecessors))


def check_antecedents_storage_release(
    storage: StorageInterface, swhid: SWHID, predecessors: Collection[SWHID]
):
    assert isinstance(storage, PgStorage), "Need to use a `local` storage instance"
    with storage.db() as db:
        with db.transaction() as cur:
            cur.execute("""
              select distinct(release.id)
              from release
              where release.target = %s and release.target_type = %s
              limit %s
            """, (swhid.object_id, swhid.object_type.name.lower(), len(predecessors) + 1))
            results = {SWHID(object_id=line[0], object_type=ObjectType.RELEASE) for line in cur.fetchall()}

    return bool(results - set(predecessors))


def check_antecedents_storage_revision(
    storage: StorageInterface, swhid: SWHID, predecessors: Collection[SWHID]
):
    assert isinstance(storage, PgStorage), "Need to use a `local` storage instance"
    with storage.db() as db:
        with db.transaction() as cur:
            cur.execute("""
              select distinct(revision.id)
              from revision
              inner join revision_history using (id)
              where revision_history.parent_id = %s
              limit %s
            """, (swhid.object_id, len(predecessors) + 1))
            results = {SWHID(object_id=line[0], object_type=ObjectType.REVISION) for line in cur.fetchall()}

    return bool(results - set(predecessors))


def check_antecedents_storage_dir_in_rev(
    storage: StorageInterface, swhid: SWHID, predecessors: Collection[SWHID]
):
    assert isinstance(storage, PgStorage), "Need to use a `local` storage instance"
    with storage.db() as db:
        with db.transaction() as cur:
            cur.execute("""
              select distinct(revision.id)
              from revision
              where directory = %s
              limit %s
            """, (swhid.object_id, len(predecessors) + 1))
            results = {SWHID(object_id=line[0], object_type=ObjectType.REVISION) for line in cur.fetchall()}

    return bool(results - set(predecessors))


def check_antecedents_storage_directory(
    storage: StorageInterface, swhid: SWHID, predecessors: Collection[SWHID]
):
    if swhid.object_type == ObjectType.DIRECTORY:
        entries_table = 'directory_entry_dir'
        entries_column = 'dir_entries'
        min_limit = 1000
    elif swhid.object_type == ObjectType.CONTENT:
        entries_table = 'directory_entry_file'
        entries_column = 'file_entries'
        min_limit = 10000
    else:
        return False

    with storage.db() as db:
        with db.transaction() as cur:
            cur.execute(f"""
              select id
              from {entries_table}
              where target = %s
            """, (swhid.object_id,))
            entry_ids = {line[0] for line in cur.fetchall()}

    if not entry_ids:
        return False

    # needed to force an index scan
    full_limit = len(predecessors) + 1
    base_limit = max(min_limit, full_limit)

    for entry_id in entry_ids:
        with storage.db() as db:
            with db.transaction() as cur:
                cur.execute(f"""
                  select distinct(id)
                  from directory
                  where ARRAY[%s]::bigint[] <@ {entries_column}
                  limit %s
                """, (entry_id, base_limit))
                for line in cur:
                    if SWHID(object_id=line[0], object_type=ObjectType.DIRECTORY) not in predecessors:
                        return True

    return False


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
            cls="local", db="service=swh", objstorage={"cls": "memory"}
        )

        swhid = SWHID.from_string(sys.argv[1])

        graph_baseurl = "http://granet.internal.softwareheritage.org:5009/"
        graph = init_graph(swhid, pickle_filename=f"{swhid}.pickle")

        get_descendents_graph(
            graph,
            storage,
            graph_baseurl,
        )

        check_predecessors_outside_graph(graph, storage, graph_baseurl)
    finally:
        if graph:
            date = datetime.datetime.now().strftime("%Y%m%dT%H%M%S")
            pickle_name = f"{swhid}.{date}.pickle"
            logger.info("Dumping to %s", pickle_name)
            graph.write_pickle(pickle_name)
            # plot_graph(graph)
            summary(graph)
            logger.info("Predecessors found: %s", len(graph.vs.select(predecessors_outside_subgraph_eq=True)))
            logger.info("Predecessors not found: %s", len(graph.vs.select(predecessors_outside_subgraph_eq=False)))
