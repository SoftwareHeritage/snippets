import csv
import subprocess
import sys
from base64 import b64decode
from pathlib import Path

from swh.graph.shell import AtomicFileSink, Command, Rust


def build_deanonymization_table(
    base_directory: Path, base_sensitive_directory: Path, dataset_name: str
):
    # TODO: use Command.swh()?
    subprocess.run(
        f"swh datasets luigi \
        --base-directory {base_directory} \
        --base-sensitive-directory {base_sensitive_directory} \
        --dataset-name {dataset_name} \
        ExportDeanonymizationTable \
        -- \
        --local-scheduler \
        --LocalExport-export-task-type ExportGraph"
    )


def build_id_list(csv_zst_file: Path, persons_function: Path, output_file: Path):
    csv_file = csv_zst_file.parent / f"{csv_zst_file.name.split('.')[0]}.csv"
    # TODO: add pv
    (Command.zstdcat(csv_zst_file) > AtomicFileSink(csv_file)).run()
    trim_csv_file = csv_zst_file.parent / f"{csv_zst_file.name.split('.')[0]}.trim.csv"

    with open(csv_file, "r") as read_file:
        with open(trim_csv_file, "w") as write_file:
            reader = csv.reader(read_file)
            writer = csv.writer(write_file)
            next(reader, None)  # skip the header
            for sha256_base64, base64, escaped in reader:
                writer.writerow((b64decode(sha256_base64)))

    return (
        Command.cat(trim_csv_file)
        | Rust(
            "swh-graph-hash",
            "persons",
            "--mph-algo",
            "pthash",
            "--mph",
            persons_function,
        )
        > AtomicFileSink(output_file)
    ).run()


def main(
    base_directory: str | Path,
    base_sensitive_directory: str | Path,
    dataset_name: str,
    output_file: str | Path,
):
    base_directory = Path(base_directory)
    base_sensitive_directory = Path(base_sensitive_directory)
    output_file = Path(output_file)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    assert base_directory.is_dir()
    assert base_sensitive_directory.is_dir()

    # build_deanonymization_table(base_directory, base_sensitive_directory, dataset_name)

    csv_file = (
        base_sensitive_directory / dataset_name / "persons_sha256_to_name.csv.zst"
    )
    assert csv_file.is_file()

    persons_function = (
        base_directory / dataset_name / "compressed" / "graph.persons.pthash"
    )
    assert persons_function.is_file()

    build_id_list(csv_file, persons_function, output_file)


if __name__ == "__main__":
    # swh datasets luigi \
    # --base-directory /srv/softwareheritage/ssd/data/varasterix/datasets/ \
    # --base-sensitive-directory /srv/softwareheritage/ssd/data/varasterix/datasets-sensitive/ \
    # --dataset-name 2025-05-18-history-hosting \
    # ExportDeanonymizationTable \
    # -- \
    # --local-scheduler \
    # --LocalExport-export-task-type ExportGraph

    # main(
    #     base_directory="/srv/softwareheritage/ssd/data/varasterix/datasets/",
    #     base_sensitive_directory="/srv/softwareheritage/ssd/data/varasterix/datasets-sensitive/",
    #     dataset_name="2025-05-18-history-hosting",
    #     output_file="deanonymized-persons.csv",
    # )

    # deanonymization_table_path=/srv/softwareheritage/ssd/data/varasterix/datasets-sensitive/2025-05-18-history-hosting/persons_sha256_to_name.csv.zst

    main(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4])
