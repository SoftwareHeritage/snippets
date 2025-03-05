use anyhow::Result;
use clap::Parser;
use std::path::PathBuf;
use swh_graph::labels::Visit;
use swh_graph::labels::VisitStatus;

use swh_graph::graph::*;
use swh_graph::NodeType;

use chrono::DateTime;
use chrono::Utc;

#[derive(Parser, Debug)]
#[command()]
/// Iterate on SWH graph nodes and stream the following info for each origin
/// matching some requirements:
///
/// - latest full snapshot SWHID
///
/// - most recent tip revision SWHID in that snapshot
///
/// - SWHID of directory targeted by the revision
struct Args {
    graph_path: PathBuf,
}

fn get_most_recent_snapshot<G: SwhFullGraph>(
    graph: &G,
    origin_node: &NodeId,
) -> Option<(NodeId, DateTime<Utc>)> {
    let mut succ_labels: Vec<(usize, Visit)> = graph
        .untyped_labeled_successors(*origin_node)
        .flatten_labels()
        .into_iter()
        .map(|(usize, label)| (usize, Visit::from(label)))
        .collect::<Vec<(usize, Visit)>>();

    succ_labels.sort_by(|(_a, b), (_c, d)| d.timestamp().cmp(&b.timestamp()));

    for (succ, visit) in &succ_labels {
        if visit.status() == VisitStatus::Full {
            return Some((
                *succ,
                DateTime::from_timestamp(visit.timestamp() as i64, 0).unwrap(),
            ));
        }
    }
    None
}

fn get_most_recent_tip_revision<G: SwhFullGraph>(
    graph: &G,
    snapshot_node: &NodeId,
) -> Option<(NodeId, DateTime<Utc>)> {
    let mut ret = 0;
    let mut max_timestamp = 0;
    for succ in graph.successors(*snapshot_node) {
        if graph.properties().node_type(succ) == NodeType::Revision {
            if let Some(timestamp) = graph.properties().committer_timestamp(succ) {
                if timestamp > max_timestamp {
                    ret = succ;
                    max_timestamp = timestamp;
                }
            }
        }
    }

    Some((ret, DateTime::from_timestamp(max_timestamp, 0).unwrap()))
}

fn get_target_directory<G: SwhFullGraph>(graph: &G, revision_node: &NodeId) -> Option<NodeId> {
    graph
        .successors(*revision_node)
        .into_iter()
        .find(|&succ| graph.properties().node_type(succ) == NodeType::Directory)
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let args = Args::parse();
    env_logger::Builder::from_env(env_logger::Env::default().default_filter_or("info")).init();

    log::info!("Loading graph");
    let graph = swh_graph::graph::load_full::<swh_graph::mph::DynMphf>(args.graph_path)
        .expect("Could not load graph");
    log::info!("Graph loaded");

    for node in 0..graph.num_nodes() {
        if graph.properties().node_type(node) == NodeType::Origin {
            let message = graph
                .properties()
                .message(node)
                .expect("Missing origin URL");
            let url = String::from_utf8_lossy(&message);
            if let Some((snapshot_node, visit_date)) = get_most_recent_snapshot(&graph, &node) {
                let snapshot_swhid = graph.properties().swhid(snapshot_node);
                if let Some((revision_node, commiter_date)) =
                    get_most_recent_tip_revision(&graph, &snapshot_node)
                {
                    let revision_swhid = graph.properties().swhid(revision_node);
                    if let Some(directory_node) = get_target_directory(&graph, &revision_node) {
                        let directory_swhid = graph.properties().swhid(directory_node);
                        println!("For origin with URL: {}", url);
                        println!(
                            "- latest full snapshot (produced on {}): {}",
                            visit_date.format("%Y-%m-%d %H:%M:%S"),
                            snapshot_swhid
                        );
                        println!(
                            "- most recent revision ({}): {}",
                            commiter_date.format("%Y-%m-%d %H:%M:%S"),
                            revision_swhid
                        );
                        println!("- directory targeted by revision: {}\n", directory_swhid);
                    }
                }
            }
        }
    }

    Ok(())
}
