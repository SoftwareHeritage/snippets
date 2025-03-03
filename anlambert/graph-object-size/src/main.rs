use anyhow::{Context, Result};
use clap::Parser;
use std::collections::{HashSet, VecDeque};
use std::path::PathBuf;
use std::time::Instant;

use human_bytes::human_bytes;

use swh_graph::graph::*;
use swh_graph::mph::DynMphf;
use swh_graph::NodeType;

#[derive(Parser, Debug)]
#[command()]
/// Compute a set of metrics for the SWHID passed as parameter by 
/// performing a BFS from the associated node in the SWH graph:
/// 
/// - number of induced subgraph nodes
/// 
/// - total number of content objects
/// 
/// - total number of skipped contents
/// 
/// - total content objects size in bytes
struct Args {
    graph_path: PathBuf,
    #[arg(long)]
    swhid: String,
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let args = Args::parse();
    env_logger::Builder::from_env(env_logger::Env::default().default_filter_or("info")).init();

    log::info!("Loading graph");
    let graph = swh_graph::graph::SwhUnidirectionalGraph::new(args.graph_path)
        .context("Could not load graph")?
        .init_properties()
        .load_properties(|props| props.load_maps::<DynMphf>())
        .context("Could not load maps")?
        .load_properties(|props| props.load_contents())
        .context("Could not load content properties")?;
    log::info!("Graph loaded");

    let nodeid = graph.properties().node_id_from_string_swhid(&args.swhid)?;

    println!("Node id for SWHID {}: {}\n", &args.swhid, nodeid);

    println!("Performing BFS from provided node and computing some metrics");

    let now = Instant::now();

    let mut queue = VecDeque::new();
    let mut visited = HashSet::new();

    queue.push_back(nodeid);
    visited.insert(nodeid);

    let mut total_contents_size = 0;
    let mut total_nb_nodes = 0;
    let mut total_nb_contents = 0;
    let mut total_nb_skipped_contents = 0;

    while let Some(node) = queue.pop_front() {
        total_nb_nodes += 1;
        if graph.properties().node_type(node) == NodeType::Content {
            let size = graph
                .properties()
                .content_length(node)
                .expect("Missing content length");
            let skipped_content = graph.properties().is_skipped_content(node);
            if !skipped_content {
                total_contents_size += size;
                total_nb_contents += 1;
            } else {
                total_nb_skipped_contents += 1;
            }
        }

        for succ in graph.successors(node) {
            if !visited.contains(&succ) {
                queue.push_back(succ);
                visited.insert(succ);
            }
        }
    }

    let elapsed = now.elapsed();
    println!("BFS execution time: {:.2?}\n", elapsed);

    println!("number of subgraph nodes: {}", total_nb_nodes);
    println!("number of contents: {}", total_nb_contents);
    println!("number of skipped contents: {}", total_nb_skipped_contents);
    println!("total contents size in bytes: {}", human_bytes(total_contents_size as f64));

    Ok(())
}
