"""Convert native featureCounts output using an explicit BAM-to-sample mapping."""
import argparse
import csv
from pathlib import Path


def convert(source: Path, mapping: Path, destination: Path) -> None:
    with mapping.open() as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        if not {"bam", "sample"}.issubset(reader.fieldnames or []):
            raise ValueError("Mapping requires bam and sample columns")
        pairs = list(reader)
    if len(pairs) < 4 or any(not row["bam"].strip() or not row["sample"].strip() for row in pairs):
        raise ValueError("Review at least four BAM-to-sample mappings")
    if len({row["bam"] for row in pairs}) != len(pairs) or len({row["sample"] for row in pairs}) != len(pairs):
        raise ValueError("BAM paths and sample IDs must each be unique")
    sample_by_bam = {row["bam"]: row["sample"] for row in pairs}
    with source.open() as handle:
        reader = csv.reader((line for line in handle if not line.startswith("#")), delimiter="\t")
        header = next(reader)
        if header[:6] != ["Geneid", "Chr", "Start", "End", "Strand", "Length"] or len(set(header)) != len(header):
            raise ValueError("Expected the native featureCounts header")
        if set(header[6:]) != set(sample_by_bam):
            raise ValueError("Map the exact BAM column names in featureCounts; no filename guessing is performed")
        rows = []; seen = set()
        for row in reader:
            if len(row) != len(header) or not row[0] or row[0] in seen:
                raise ValueError("Missing/duplicate gene or malformed row")
            if any(not value.isascii() or not value.isdigit() for value in row[6:]):
                raise ValueError("Only nonnegative integer assignments can enter the raw-count matrix")
            seen.add(row[0]); rows.append([row[0], *row[6:]])
    if len(rows) < 2:
        raise ValueError("Too few gene rows")
    with destination.open("w", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t")
        writer.writerow(["gene", *[sample_by_bam[name] for name in header[6:]]])
        writer.writerows(rows)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--bam-samples", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    convert(args.input, args.bam_samples, args.output)
