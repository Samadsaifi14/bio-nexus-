#!/usr/bin/env python3
"""Prepare the real GSE67196 sALS-versus-control cerebellum benchmark.

Inputs are the official GEO processed count matrix and GEO family SOFT metadata.
The script selects the declared 8-control/10-sALS cerebellum cohort, resolves every
sample back to its GEO/GSM record and deposited count column, aggregates only rows
that share the same deposited GeneID, and writes raw integer counts plus auditable
source mappings. It does not normalize, impute, or select genes by outcome.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import re
from collections import OrderedDict
from pathlib import Path
from typing import Dict, Iterable, List

EXPECTED_SOURCE_ROWS = 23398
EXPECTED_UNIQUE_GENE_IDS = 23344
EXPECTED_ALL_ZERO_SELECTED = 2294


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def open_text(path: Path):
    if path.suffix == ".gz":
        return gzip.open(path, "rt", encoding="utf-8", errors="replace")
    return path.open("r", encoding="utf-8", errors="replace")


def natural_key(value: str):
    return [int(x) if x.isdigit() else x.lower() for x in re.split(r"(\d+)", value)]


def norm(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


def parse_soft(path: Path) -> Dict[str, dict]:
    samples: Dict[str, dict] = {}
    current = None
    with open_text(path) as handle:
        for raw in handle:
            line = raw.rstrip("\n\r")
            if line.startswith("^SAMPLE = "):
                gsm = line.split("=", 1)[1].strip()
                current = {"gsm": gsm, "title": "", "characteristics": []}
                samples[gsm] = current
            elif current is not None and line.startswith("!Sample_title = "):
                current["title"] = line.split("=", 1)[1].strip()
            elif current is not None and line.startswith("!Sample_characteristics_ch1 = "):
                current["characteristics"].append(line.split("=", 1)[1].strip())
    if not samples:
        raise RuntimeError("No SAMPLE records were found in the GEO SOFT file")
    return samples


def characteristic_value(chars: Iterable[str], key: str) -> str:
    prefix = key.lower() + ":"
    for item in chars:
        if item.lower().startswith(prefix):
            return item.split(":", 1)[1].strip()
    return ""


def classify_samples(samples: Dict[str, dict]) -> List[dict]:
    selected: List[dict] = []
    for rec in samples.values():
        tissue = characteristic_value(rec["characteristics"], "tissue")
        genotype = characteristic_value(rec["characteristics"], "genotype")
        if "cerebell" not in tissue.lower():
            continue
        gl = re.sub(r"[\s_-]+", "", genotype.lower())
        if gl in {"control", "healthy", "normal"}:
            condition = "healthy"
        elif gl in {"sals", "sporadicals", "sporadicalsals"}:
            condition = "SALS"
        else:
            continue
        selected.append({
            "gsm": rec["gsm"],
            "title": rec["title"],
            "tissue": tissue,
            "genotype": genotype,
            "condition": condition,
        })

    healthy = sorted(
        [x for x in selected if x["condition"] == "healthy"],
        key=lambda x: natural_key(x["title"]),
    )
    sals = sorted(
        [x for x in selected if x["condition"] == "SALS"],
        key=lambda x: natural_key(x["title"]),
    )
    if len(healthy) != 8 or len(sals) != 10:
        raise RuntimeError(
            f"Expected 8 healthy and 10 sALS cerebellum samples; "
            f"found {len(healthy)} healthy and {len(sals)} sALS"
        )
    return healthy + sals


def resolve_count_column(header: List[str], rec: dict) -> str:
    for candidate in (rec["title"], rec["gsm"]):
        if candidate in header:
            return candidate
    normalized = {norm(h): h for h in header}
    for candidate in (rec["title"], rec["gsm"]):
        if norm(candidate) in normalized:
            return normalized[norm(candidate)]

    # GEO titles such as 73_cereb_a correspond to deposited columns such as
    # ALS073_cereb. Resolve this explicitly rather than by column position.
    match = re.match(r"^(\d+)_cereb(?:_[A-Za-z])?$", rec["title"], flags=re.IGNORECASE)
    if match:
        deposited = f"ALS{int(match.group(1)):03d}_cereb"
        if deposited in header:
            return deposited

    for candidate in (rec["title"], rec["gsm"]):
        key = norm(candidate)
        matches = [h for h in header if key and (key in norm(h) or norm(h) in key)]
        if len(matches) == 1:
            return matches[0]
    raise RuntimeError(
        f"Could not map GEO sample {rec['gsm']} / {rec['title']!r} to a count column"
    )


def prepare(counts_path: Path, soft_path: Path, outdir: Path) -> None:
    outdir.mkdir(parents=True, exist_ok=True)
    samples = classify_samples(parse_soft(soft_path))

    with open_text(counts_path) as handle:
        reader = csv.reader(handle, delimiter="\t")
        header = next(reader)
        hnorm = {norm(name): idx for idx, name in enumerate(header)}
        gene_index = hnorm.get("geneid")
        chr_index = hnorm.get("chr")
        if gene_index is None:
            raise RuntimeError(f"GEO matrix does not contain a GeneID column: {header[:10]!r}")

        mapped: List[dict] = []
        healthy_i = sals_i = 0
        for sample in samples:
            source_col = resolve_count_column(header, sample)
            if sample["condition"] == "healthy":
                healthy_i += 1
                local_name = f"Cer_healthy{healthy_i}"
            else:
                sals_i += 1
                local_name = f"Cer_SALS{sals_i}"
            mapped.append({**sample, "source_column": source_col, "local_sample": local_name})
        source_indices = [header.index(x["source_column"]) for x in mapped]

        aggregated: OrderedDict[str, dict] = OrderedDict()
        source_rows = 0
        for source_row_number, row in enumerate(reader, start=2):
            if not row or len(row) < len(header):
                continue
            gene = row[gene_index].strip()
            if not gene:
                continue
            source_rows += 1
            values: List[int] = []
            for index in source_indices:
                raw_value = row[index].strip()
                try:
                    numeric = float(raw_value)
                except ValueError as exc:
                    raise RuntimeError(f"Non-numeric count for GeneID {gene}: {raw_value!r}") from exc
                if numeric < 0 or abs(numeric - round(numeric)) > 1e-8:
                    raise RuntimeError(
                        f"Count for GeneID {gene} is not a non-negative integer: {raw_value!r}"
                    )
                values.append(int(round(numeric)))

            if gene not in aggregated:
                aggregated[gene] = {
                    "counts": [0] * len(values),
                    "source_rows": [],
                    "chromosomes": [],
                }
            agg = aggregated[gene]
            agg["counts"] = [a + b for a, b in zip(agg["counts"], values)]
            agg["source_rows"].append(source_row_number)
            if chr_index is not None and row[chr_index].strip():
                agg["chromosomes"].append(row[chr_index].strip())

    if source_rows != EXPECTED_SOURCE_ROWS:
        raise RuntimeError(
            f"Expected {EXPECTED_SOURCE_ROWS:,} deposited source rows; found {source_rows:,}"
        )
    if len(aggregated) != EXPECTED_UNIQUE_GENE_IDS:
        raise RuntimeError(
            f"Expected {EXPECTED_UNIQUE_GENE_IDS:,} unique deposited GeneID values; "
            f"found {len(aggregated):,}"
        )

    all_zero = [gene for gene, rec in aggregated.items() if sum(rec["counts"]) == 0]
    if len(all_zero) != EXPECTED_ALL_ZERO_SELECTED:
        raise RuntimeError(
            f"Expected {EXPECTED_ALL_ZERO_SELECTED:,} all-zero genes in the selected cohort; "
            f"found {len(all_zero):,}"
        )

    # Keep every unique deposited GeneID in the raw statistical input. The
    # application's declared DESeq2 prefilter is responsible for removing rows
    # without sufficient counts. This avoids creating a hidden source-preparation
    # filter merely to reproduce a teaching-file row count.
    counts_out = outdir / "Cer_SALS_GSE67196_counts.tsv"
    with counts_out.open("w", newline="", encoding="utf-8") as out:
        writer = csv.writer(out, delimiter="\t", lineterminator="\n")
        writer.writerow(["gene"] + [x["local_sample"] for x in mapped])
        for gene, rec in aggregated.items():
            writer.writerow([gene] + rec["counts"])

    metadata_out = outdir / "Cer_SALS_GSE67196_metadata.tsv"
    metadata_fields = [
        "sample", "condition", "source_gsm", "source_title", "source_genotype", "tissue"
    ]
    with metadata_out.open("w", newline="", encoding="utf-8") as out:
        writer = csv.DictWriter(out, delimiter="\t", lineterminator="\n", fieldnames=metadata_fields)
        writer.writeheader()
        for rec in mapped:
            writer.writerow({
                "sample": rec["local_sample"],
                "condition": rec["condition"],
                "source_gsm": rec["gsm"],
                "source_title": rec["title"],
                "source_genotype": rec["genotype"],
                "tissue": rec["tissue"],
            })

    sample_mapping_out = outdir / "source_sample_mapping.tsv"
    mapping_fields = [
        "local_sample", "condition", "source_gsm", "source_title", "source_column",
        "source_genotype", "tissue"
    ]
    with sample_mapping_out.open("w", newline="", encoding="utf-8") as out:
        writer = csv.DictWriter(out, delimiter="\t", lineterminator="\n", fieldnames=mapping_fields)
        writer.writeheader()
        for rec in mapped:
            writer.writerow({
                "local_sample": rec["local_sample"],
                "condition": rec["condition"],
                "source_gsm": rec["gsm"],
                "source_title": rec["title"],
                "source_column": rec["source_column"],
                "source_genotype": rec["genotype"],
                "tissue": rec["tissue"],
            })

    gene_mapping_out = outdir / "source_gene_id_mapping.tsv"
    with gene_mapping_out.open("w", newline="", encoding="utf-8") as out:
        writer = csv.writer(out, delimiter="\t", lineterminator="\n")
        writer.writerow([
            "gene", "source_row_count", "source_rows", "chromosomes",
            "selected_cohort_total_count", "all_zero_selected_cohort"
        ])
        for gene, rec in aggregated.items():
            total = sum(rec["counts"])
            writer.writerow([
                gene,
                len(rec["source_rows"]),
                ",".join(map(str, rec["source_rows"])),
                ",".join(dict.fromkeys(rec["chromosomes"])),
                total,
                str(total == 0).lower(),
            ])

    repeated_gene_ids = sum(1 for rec in aggregated.values() if len(rec["source_rows"]) > 1)
    repeated_source_rows = sum(len(rec["source_rows"]) - 1 for rec in aggregated.values())
    provenance = {
        "dataset": "GSE67196",
        "bioproject": "PRJNA279249",
        "sra_study": "SRP056477",
        "title": "Distinct brain transcriptome profiles in c9orf72-associated and sporadic ALS",
        "data_type": "public human post-mortem brain RNA-seq gene-count matrix",
        "analysis_subset": "cerebellum: healthy controls versus sporadic ALS",
        "deposited_source_rows": source_rows,
        "unique_deposited_gene_ids": len(aggregated),
        "repeated_gene_ids": repeated_gene_ids,
        "additional_repeated_source_rows": repeated_source_rows,
        "all_zero_unique_genes_in_selected_cohort": len(all_zero),
        "statistical_input_gene_ids": len(aggregated),
        "gene_aggregation_policy": (
            "Rows sharing an identical deposited GeneID are summed sample-wise. "
            "No normalization, imputation, or outcome-dependent filtering is applied."
        ),
        "source_preparation_filter_policy": (
            "No GeneID is removed during source preparation. All-zero and low-count rows are "
            "passed to the same declared DESeq2 prefilter used by the BioNexus application."
        ),
        "healthy_samples": 8,
        "sals_samples": 10,
        "source_count_filename": counts_path.name,
        "source_count_sha256": sha256_file(counts_path),
        "source_soft_filename": soft_path.name,
        "source_soft_sha256": sha256_file(soft_path),
        "derived_count_sha256": sha256_file(counts_out),
        "derived_metadata_sha256": sha256_file(metadata_out),
        "sample_mapping_sha256": sha256_file(sample_mapping_out),
        "gene_mapping_sha256": sha256_file(gene_mapping_out),
        "selection_rule": (
            "GEO metadata tissue contains 'cerebell' and genotype is healthy/control or sALS; "
            "exactly 8 controls and 10 sALS are required."
        ),
        "samples": mapped,
    }
    (outdir / "source_provenance.json").write_text(
        json.dumps(provenance, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--counts", required=True, type=Path)
    parser.add_argument("--soft", required=True, type=Path)
    parser.add_argument("--outdir", required=True, type=Path)
    args = parser.parse_args()
    prepare(args.counts, args.soft, args.outdir)
