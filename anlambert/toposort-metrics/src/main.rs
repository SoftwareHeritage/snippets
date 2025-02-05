use anyhow::{Context, Result};
use clap::Parser;
use postgres::{Client, NoTls};
use std::collections::HashMap;
use std::path::PathBuf;

use swh_graph::graph::*;
use swh_graph::mph::DynMphf;
use swh_graph::{NodeType, SWHID};

use swh_graph_topology::generations::GenerationsReader;

#[derive(Parser, Debug)]
#[command()]
/// Reads a topological order .bitstream file, and streams it as a CSV with header
/// "swhid,generation"
struct Args {
    graph_path: PathBuf,
    #[arg(long)]
    /// Path from where to read the input order, and the accompanying .ef delimiting offsets between
    /// generations
    order: PathBuf,
}

fn write_dir_length(
    client: &mut Client,
    dir_swhid: SWHID,
    length: u64,
) -> Result<(), Box<dyn std::error::Error>> {
    client.execute(
        "INSERT INTO toposort_metrics (swhid, length) VALUES ($1, $2) ON CONFLICT DO UPDATE",
        &[&dir_swhid.to_string(), &(length as i64)],
    )?;
    Ok(())
}

fn read_dir_length(
    client: &mut Client,
    dir_swhid: SWHID,
) -> Result<u64, Box<dyn std::error::Error>> {
    let row = client.query_one(
        "SELECT length FROM toposort_metrics WHERE swhid = $1",
        &[&dir_swhid.to_string()],
    )?;
    let length: i64 = row.get("length");
    Ok(length as u64)
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let args = Args::parse();
    env_logger::Builder::from_env(env_logger::Env::default().default_filter_or("info")).init();
    // let mut client = Client::connect("host=localhost user=anlambert password=toto", NoTls)?;
    // client.batch_execute(
    //     "
    // CREATE TABLE IF NOT EXISTS toposort_metrics (
    //     swhid   TEXT NOT NULL PRIMARY KEY,
    //     length  BIGINT
    // )
    // ",
    // )?;

    log::info!("Loading graph");
    let graph = swh_graph::graph::SwhUnidirectionalGraph::new(args.graph_path)
        .context("Could not load graph")?
        .load_labels()
        .context("Could not load labels")?
        .init_properties()
        .load_properties(|props| props.load_maps::<DynMphf>())
        .context("Could not load maps")?
        .load_properties(|props| props.load_contents())
        .context("Could not load content properties")?;

    log::info!("Graph loaded: {} nodes / {} edges", graph.num_nodes(), graph.num_arcs());

    log::info!("Loading order");
    let reader = GenerationsReader::new(args.order).context("Could not load topological order")?;

    log::info!("Computing graph metrics");

    let mut dir_lengths = HashMap::new();

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
                    // length += read_dir_length(&mut client, succ_swhid)?;
                    let dir_length = dir_lengths
                        .get(&succ_swhid.to_string())
                        .expect("Invalid topological ordering");
                    length += dir_length;
                } else if graph.properties().node_type(succ) == NodeType::Content {
                    length += graph
                        .properties()
                        .content_length(succ)
                        .expect("Missing content length");
                }
            }
            // write_dir_length(&mut client, dir_swhid, length)?;
            dir_lengths.insert(dir_swhid.to_string(), length);
        };
    }


    log::info!("Graph metrics computed");

    let mut hash_vec: Vec<(&String, &u64)> = dir_lengths.iter().collect();
    hash_vec.sort_by(|a, b| a.1.cmp(b.1));

    for (key, value) in &hash_vec {
        println!("{key}: {value}");
    }

    Ok(())
}
