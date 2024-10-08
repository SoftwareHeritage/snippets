#!/usr/bin/env python3

# Copyright (C) 2024  The Software Heritage developers
# See the AUTHORS file at the top-level directory of this distribution
# License: GNU General Public License version 3, or any later version
# See top-level LICENSE file for more information

import os

import boto3
import click
import pyspark
from botocore import UNSIGNED
from botocore.client import Config


def get_latest_graph_dataset_date(bucket_name, folder_name):
    s3_client = boto3.client("s3", config=Config(signature_version=UNSIGNED))
    paginator = s3_client.get_paginator("list_objects_v2")
    dates = set()
    for page in paginator.paginate(Bucket=bucket_name, Prefix=folder_name):
        dates.update(sorted(obj["Key"].split("/")[1] for obj in page.get("Contents")))
    return list(sorted(dates))[-1]


@click.command()
@click.option(
    "--graph-dataset-date",
    default=None,
    show_default=True,
    help=(
        "Date of the Software Heritage graph dataset, "
        "use the latest one if not provided"
    ),
)
@click.option(
    "--csv-dump-path",
    default="origins",
    show_default=True,
    help="Paths where CSV files containing origin URLs are dumped",
)
def run(graph_dataset_date, csv_dump_path):
    """Dump all origin URLs from Software heritage graph dataset to CSV files."""
    bucket_name = "softwareheritage"
    folder_name = "graph"
    if graph_dataset_date is None:
        graph_dataset_date = get_latest_graph_dataset_date(bucket_name, folder_name)
    csv_dump_path_absolute = (
        os.path.abspath(os.path.join(os.getcwd(), csv_dump_path))
        if not csv_dump_path.startswith("/")
        else csv_dump_path
    )
    os.environ["PYSPARK_SUBMIT_ARGS"] = (
        "--packages org.apache.spark:spark-hadoop-cloud_2.12:3.2.0 pyspark-shell"
    )
    session = pyspark.sql.SparkSession.builder.config(
        "fs.s3a.aws.credentials.provider",
        "org.apache.hadoop.fs.s3a.AnonymousAWSCredentialsProvider",
    ).getOrCreate()
    df = session.sql(
        f"SELECT url FROM orc.`s3a://softwareheritage/graph/{graph_dataset_date}/orc/origin`"
    )
    print(
        "Fetching origin URLs from Software Heritage graph dataset with date "
        f"{graph_dataset_date} and dumping them to CSV files in folder {csv_dump_path_absolute}"
    )
    df.write.csv(csv_dump_path)


if __name__ == "__main__":
    run()
