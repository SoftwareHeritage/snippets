import csv
import sys
from pathlib import Path

from swh.graph.shell import AtomicFileSink, Command, Rust


def build_hashes_table(
    persons_table: Path, persons_function: Path, persons_id_table: Path
):
    persons_csv = persons_table.parent / "graph.persons.csv"
    (Command.zstdcat(persons_table) > AtomicFileSink(persons_csv)).run()

    # fmt: off
    (
        Command.cat(persons_csv)
        | Rust("swh-graph-hash", "persons", "--mph-algo", "pthash", "--mph", persons_function)
        > AtomicFileSink(persons_id_table)
    ).run()
    # fmt: on


def build_names_table(
    deanonymization_table: Path, persons_id_table: Path, persons_name_table: Path
):
    persons_csv = deanonymization_table.parent / "persons_sha256_to_name.csv"
    (Command.zstdcat(deanonymization_table) > AtomicFileSink(persons_csv)).run()

    with open(persons_id_table, "r") as ids_file:
        with open(persons_csv, "r") as persons_file:
            with open(persons_name_table, "w") as names_file:
                ids_reader = csv.reader(ids_file)
                persons_reader = csv.reader(persons_file)
                writer = csv.writer(names_file)
                for (_, base64, escaped), [id] in zip(persons_reader, ids_reader):
                    writer.writerow((id, base64, escaped))


def main(
    base_directory: str | Path,
    base_sensitive_directory: str | Path,
    dataset_name: str,
    output_dir: str | Path,
    query: str | None = None,
):
    base_directory = Path(base_directory)
    base_sensitive_directory = Path(base_sensitive_directory)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    assert base_directory.is_dir()
    assert base_sensitive_directory.is_dir()

    persons_table = (
        base_directory / dataset_name / "compressed" / "graph.persons.csv.zst"
    )
    if not persons_table.is_file():
        print(f"{persons_table} not found...")
        print("Run the following to generate it:")
        print(
            f"swh graph compress \
                --input-dataset {base_directory / dataset_name / 'orc'} \
                --sensitive-input-dataset {base_sensitive_directory / dataset_name / 'orc'} \
                --output-directory {base_directory / dataset_name / 'compressed'} \
                --sensitive-output-directory {base_directory / dataset_name / 'compressed'} \
                --steps EXTRACT_PERSONS \
                --check-flavor none"
        )
        raise FileNotFoundError

    persons_function = (
        base_directory / dataset_name / "compressed" / "graph.persons.pthash"
    )
    assert persons_function.is_file(), f"{persons_function} not found..."

    deanonymization_table = (
        base_sensitive_directory / dataset_name / "persons_sha256_to_name.csv.zst"
    )

    if not deanonymization_table.is_file():
        print(f"{deanonymization_table} not found...")
        print("Run the following to generate it:")
        print(
            f"swh datasets luigi \
                --base-directory {base_directory} \
                --base-sensitive-directory {base_sensitive_directory} \
                --dataset-name {dataset_name} \
                ExportDeanonymizationTable \
                -- \
                --local-scheduler \
                --LocalExport-export-task-type ExportGraph"
        )
        raise FileNotFoundError

    persons_id_table = output_dir / "persons_sha256_to_id.csv"

    build_hashes_table(persons_table, persons_function, persons_id_table)
    assert persons_id_table.is_file(), f"{persons_id_table} not found..."

    persons_name_table = output_dir / "persons_id_to_name.csv"

    build_names_table(deanonymization_table, persons_id_table, persons_name_table)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4])
