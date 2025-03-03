use anyhow::{Context, Result};
use clap::Parser;
use std::collections::HashMap;
use std::path::PathBuf;
use std::time::Instant;

use human_bytes::human_bytes;

use swh_graph::graph::*;
use swh_graph::mph::DynMphf;
use swh_graph::NodeType;

use swh_graph_topology::generations::GenerationsReader;

#[derive(Parser, Debug)]
#[command()]
/// Reads a backward topological order .bitstream file, and computes:
/// 
/// - sizes of all directories in a linear pass thanks to that order
/// 
/// - total content objects size
struct Args {
    graph_path: PathBuf,
    #[arg(long)]
    /// Path from where to read the input order, and the accompanying .ef delimiting offsets between
    /// generations
    order: PathBuf,
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

    log::info!(
        "Graph loaded: {} nodes / {} edges",
        graph.num_nodes(),
        graph.num_arcs()
    );

    log::info!("Loading order");
    let reader = GenerationsReader::new(args.order).context("Could not load topological order")?;

    log::info!("Computing graph metrics");

    let now = Instant::now();

    let mut dir_lengths = HashMap::new();
    let mut total_contents_size = 0;

    for (_, node) in reader
        .iter_nodes()
        .context("Could not read topological order")?
    {
        if graph.properties().node_type(node) == NodeType::Directory {
            // println!("directory {}", graph.properties().swhid(node));
            let dir_swhid = graph.properties().swhid(node);
            let mut length: u64 = 0;
            for succ in graph.successors(node) {
                let succ_swhid = graph.properties().swhid(succ);
                if graph.properties().node_type(succ) == NodeType::Directory {
                    let dir_length = dir_lengths
                        .get(&succ_swhid.to_string())
                        .expect("Invalid topological ordering");
                    length += dir_length;
                } else if graph.properties().node_type(succ) == NodeType::Content {
                    let size = graph
                        .properties()
                        .content_length(succ)
                        .expect("Missing content length");
                    let skipped_content = graph.properties().is_skipped_content(succ);
                    if !skipped_content {
                        length += size;
                    }
                }
            }
            dir_lengths.insert(dir_swhid.to_string(), length);
        } else if graph.properties().node_type(node) == NodeType::Content {
            let size = graph
                .properties()
                .content_length(node)
                .expect("Missing content length");
            let skipped_content = graph.properties().is_skipped_content(node);
            if !skipped_content {
                total_contents_size += size;
            }
        };
    }
    let elapsed = now.elapsed();
    log::info!("Graph metrics computed in {:.2?}", elapsed);

    // let mut hash_vec: Vec<(&String, &u64)> = dir_lengths.iter().collect();
    // hash_vec.sort_by(|a, b| a.1.cmp(b.1));

    // for (key, value) in &hash_vec {
    //     println!("{key}: {value}");
    // }

    println!("Total contents size: {}", human_bytes(total_contents_size as f64));

    Ok(())
}
