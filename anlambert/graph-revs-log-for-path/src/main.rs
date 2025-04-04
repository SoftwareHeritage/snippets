use anyhow::{anyhow, Result};
use clap::Parser;
use std::collections::BinaryHeap;
use std::collections::HashSet;
use std::path::PathBuf;
use std::str::FromStr;

use swh_graph::labels::{EdgeLabel, FilenameId};
use swh_graph::SWHID;
use swh_graph::graph::*;
use swh_graph::NodeType;

#[derive(Parser, Debug)]
#[command(verbatim_doc_comment)]
/// Revisions walker for the SWH graph starting from a given revision and
/// returning revisions where a specific path in the targeted source trees
/// was modified, in other terms it allows to get the commits history for a
/// specific file or directory in a repository.
///
/// It has a behaviour similar to what "git log" offers by default,
/// meaning the returned history is simplified in order to only show
/// relevant revisions.
///
/// See https://git-scm.com/docs/git-log#_history_simplification for
/// more details.
///
/// Please note that to avoid walking the entire history, the iteration
/// will stop once a revision where the path has been added is found.
struct Args {
    graph_path: PathBuf,
    #[arg(long)]
    start_rev_swhid: String,
    #[arg(long)]
    path: String,
}

fn directory_entry_get_by_path<G: SwhFullGraph>(
    graph: &G,
    rev: NodeId,
    path_parts: &[FilenameId],
) -> Result<Option<NodeId>> {
    let props = graph.properties();
    let mut current_dir = graph
        .successors(rev)
        .into_iter()
        .find(|&succ| props.node_type(succ) == NodeType::Directory)
        .ok_or_else(|| anyhow!("{} has no root directory", graph.properties().swhid(rev)))?;

    for &path_part in path_parts {
        let mut dir_entry_for_name = None;
        for (succ, labels) in graph.labeled_successors(current_dir) {
            for label in labels {
                if let EdgeLabel::DirEntry(dentry) = label {
                    if dentry.filename_id() == path_part {
                        dir_entry_for_name = Some(succ);
                    }
                }
            }
        }
        match dir_entry_for_name {
            None => return Ok(None), // path does not exist
            Some(dir_entry_for_name) => current_dir = dir_entry_for_name,
        }
    }
    Ok(Some(current_dir))
}

fn process_revision<G: SwhFullGraph>(graph: &G, rev: &NodeId, heap: &mut BinaryHeap<(i64, usize)>) {
    let rev_committer_date = match graph.properties().committer_timestamp(*rev) {
        None => heap.len() as i64,
        Some(ts) => ts,
    };
    heap.push((rev_committer_date, *rev));
}

fn process_parent_revisions<G: SwhFullGraph>(
    graph: &G,
    rev: NodeId,
    path_parts: &[FilenameId],
    heap: &mut BinaryHeap<(i64, usize)>,
) -> Result<(bool, bool)> {
    let rev_path_id = directory_entry_get_by_path(graph, rev, path_parts)?;
    let mut parents = Vec::new();
    for succ in graph.successors(rev) {
        if graph.properties().node_type(succ) == NodeType::Revision {
            parents.push(succ);
        }
    }

    if parents.is_empty() {
        return Ok((rev_path_id.is_some(), false));
    }

    let parent_rev_path_ids = parents
        .clone()
        .into_iter()
        .map(|parent| directory_entry_get_by_path(graph, parent, path_parts))
        .collect::<Result<Vec<Option<usize>>, _>>()?;
    let different_path_ids = parent_rev_path_ids
        .clone()
        .into_iter()
        .all(|parent_rev_path_id| parent_rev_path_id != rev_path_id);

    if let Some(rev_path_id) = rev_path_id {
        if parents.len() == 1 {
            process_revision(graph, parents.first().unwrap(), heap);
        } else {
            for i in 0..parents.len() {
                if different_path_ids || parent_rev_path_ids[i] == Some(rev_path_id) {
                    process_revision(graph, &parents[i], heap);
                    if !different_path_ids {
                        break;
                    }
                }
            }
        }
        if Some(rev_path_id) != parent_rev_path_ids[0] && different_path_ids {
            return Ok((
                true,
                parent_rev_path_ids
                    .into_iter()
                    .all(|parent_rev_path_id| parent_rev_path_id.is_none()),
            ));
        }
    } else {
        for parent in parents {
            process_revision(graph, &parent, heap);
        }
    }
    Ok((false, false))
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let args = Args::parse();
    env_logger::Builder::from_env(env_logger::Env::default().default_filter_or("info")).init();

    let start_rev_swhid = SWHID::from_str(&args.start_rev_swhid)?;

    if start_rev_swhid.node_type != NodeType::Revision {
        panic!("Input SWHID must target a revision");
    }

    log::info!("Loading graph");
    let graph = swh_graph::graph::load_full::<swh_graph::mph::DynMphf>(args.graph_path)
        .expect("Could not load graph");
    log::info!("Graph loaded");

    let nodeid = graph.properties().node_id(start_rev_swhid)?;

    let Ok(path_parts) = args
        .path
        .trim()
        .split("/")
        .map(|path_part| graph.properties().label_name_id(path_part))
        .collect::<Result<Vec<_>, _>>() else {
        // One of the path parts does not exist in the graph, which means there is no file with that name.
        return Ok(());
    };

    let mut heap = BinaryHeap::<(i64, usize)>::new();

    let mut visited = HashSet::<usize>::new();

    process_revision(&graph, &nodeid, &mut heap);

    while !heap.is_empty() {
        let (_, rev) = heap.pop().unwrap();
        if visited.contains(&rev) {
            continue;
        }
        visited.insert(rev);
        let (rev_with_path, stop_revs_walk) = process_parent_revisions(&graph, rev, &path_parts, &mut heap)?;
        if rev_with_path {
            println!("{}", graph.properties().swhid(rev));
        }
        if stop_revs_walk {
            break;
        }
    }

    Ok(())
}
