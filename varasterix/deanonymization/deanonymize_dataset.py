import csv
import sys
from pathlib import Path

from swh.graph.shell import AtomicFileSink, Command, Rust
from tqdm import tqdm


def build_hashes_table(
    persons_table: Path, persons_function: Path, persons_id_table: Path
):
    persons_csv = persons_table.parent / "graph.persons.csv"
    print("Decompressing persons table...")
    # Using `zstdcat` instead of `zstdmt` to allow decompressing files that are symlinks
    (Command.zstdcat(persons_table) | Command.pv() > AtomicFileSink(persons_csv)).run()
    print("Persons table decompressed")

    # fmt: off
    (
        Command.tail(persons_csv, "-n", "+2")  # skip the first line (header)
        | Rust("swh-graph-hash", "persons", "--mph-algo", "pthash", "--mph", persons_function)
        > AtomicFileSink(persons_id_table)
    ).run()
    # fmt: on


def build_sorted_table(persons_csv, persons_id_table, sorted_table):
    with open(persons_id_table, "r") as ids_file:
        with open(persons_csv, "r") as persons_file:
            with open(sorted_table, "w") as names_file:
                ids_reader = csv.reader(ids_file)
                persons_reader = csv.reader(persons_file)
                writer = csv.writer(names_file)
                print("Writing sorted table...")
                for (sha256_base64,), (id,) in tqdm(zip(persons_reader, ids_reader)):
                    writer.writerow((sha256_base64, id))
                print("Sorted table written")


def build_names_table(
    deanonymization_table: Path, sorted_table: Path, persons_name_table: Path
):
    persons_sha256_csv = deanonymization_table.parent / "persons_sha256_to_name.csv"
    print("Decompressing deanonymization table...")
    # Using `zstdcat` instead of `zstdmt` to allow decompressing files that are symlinks
    (
        Command.zstdcat(deanonymization_table) | Command.pv()
        > AtomicFileSink(persons_sha256_csv)
    ).run()
    print("Deanonymization table decompressed")

    sha256_base64_to_id = {}
    with open(sorted_table, "r") as sorted_file:
        sorted_reader = csv.reader(sorted_file)
        print("Writing intermediary mapping...")
        for sha256_base64, id in tqdm(sorted_reader):
            sha256_base64_to_id[sha256_base64] = id
        print("Intermediary mapping written")

    with open(persons_sha256_csv, "r") as persons_file:
        with open(persons_name_table, "w") as names_file:
            persons_reader = csv.reader(persons_file)
            writer = csv.writer(names_file)
            print("Writing final mapping...")
            for sha256_base64, base64, escaped in tqdm(persons_reader):
                if sha256_base64_to_id.get(sha256_base64) is not None:
                    writer.writerow(
                        (sha256_base64_to_id[sha256_base64], base64, escaped)
                    )
            print("Final mapping written")


def main(
    base_directory: str | Path,
    base_sensitive_directory: str | Path,
    dataset_name: str,
    output_dir: str | Path,
):
    base_directory = Path(base_directory)
    base_sensitive_directory = Path(base_sensitive_directory)
    graph_path = base_directory / dataset_name / "compressed"
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    assert base_directory.is_dir()
    assert base_sensitive_directory.is_dir()
    assert graph_path.is_dir()

    persons_table = graph_path / "graph.persons.csv.zst"
    if not persons_table.is_file():
        print(f"{persons_table} not found...")
        print("Run the following to generate it:")
        print(
            f"swh graph compress \
                --input-dataset {base_directory / dataset_name / 'orc'} \
                --sensitive-input-dataset {base_sensitive_directory / dataset_name / 'orc'} \
                --output-directory {graph_path} \
                --sensitive-output-directory {base_sensitive_directory / dataset_name / 'compressed'} \
                --steps EXTRACT_PERSONS \
                --check-flavor none"
        )
        raise FileNotFoundError

    persons_function = graph_path / "graph.persons.pthash"
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
    persons_csv = persons_table.parent / "graph.persons.csv"

    build_hashes_table(persons_table, persons_function, persons_id_table)
    assert persons_csv.is_file(), f"{persons_id_table} not found..."
    assert persons_id_table.is_file(), f"{persons_id_table} not found..."

    sorted_table = output_dir / "persons_sorted.csv"

    build_sorted_table(persons_csv, persons_id_table, sorted_table)
    assert sorted_table.is_file(), f"{sorted_table} not found..."

    persons_name_table = output_dir / "persons_id_to_name.csv"

    build_names_table(deanonymization_table, sorted_table, persons_name_table)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4])
