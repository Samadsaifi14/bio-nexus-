"""Numerical checks against direct DESeq2/tximport, not source-token checks."""
import csv
import json
import os
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pytest

from app.rnaseq.expression import ExpressionParameters, _run_r, validate_artifacts

RSCRIPT = shutil.which(os.environ.get("BIONEXUS_RSCRIPT", "Rscript"))
pytestmark = pytest.mark.skipif(not RSCRIPT, reason="R scientific runtime is not installed")


def inputs(tmp_path):
    rng = np.random.default_rng(481)
    values = rng.negative_binomial(12, .12, size=(160, 8)) + 1
    values[:30, 4:] *= 4
    counts = tmp_path / "counts.tsv"
    with counts.open("w") as handle:
        writer = csv.writer(handle, delimiter="\t")
        writer.writerow(["gene", *[f"s{i}" for i in range(8)]])
        writer.writerows([f"gene{i}", *row] for i, row in enumerate(values))
    metadata = tmp_path / "metadata.tsv"
    metadata.write_text("sample\tcondition\texperimental_unit\n" + "".join(f"s{i}\t{'a' if i<4 else 'b'}\tu{i}\n" for i in range(8)))
    return counts, metadata, values


def run_direct(code, *args):
    result = subprocess.run([RSCRIPT, "-e", code, *map(str, args)], capture_output=True, text=True, timeout=180)
    assert result.returncode == 0, result.stderr


def test_qc_stops_before_testing_and_inference_matches_direct_deseq2(tmp_path):
    counts, metadata, _ = inputs(tmp_path)
    checkpoint = tmp_path / "qc.rds"; qc = tmp_path / "qc"; qc.mkdir()
    params = ExpressionParameters(reference_level="a", test_level="b", min_samples=4)
    summary = _run_r(counts, metadata, qc, params, stage="qc", checkpoint_path=checkpoint)
    validate_artifacts(qc, summary, "qc")
    assert summary["inference_performed"] is False
    assert checkpoint.exists() and not (qc / "deseq2_all_results.tsv").exists()
    out = tmp_path / "infer"; out.mkdir()
    summary = _run_r(counts, metadata, out, params, stage="infer", checkpoint_path=checkpoint)
    validate_artifacts(out, summary, "infer")
    assert isinstance(summary["design_warnings"], list)
    assert (out / "volcano_plot_data.tsv").exists()
    run_direct('''suppressPackageStartupMessages(library(DESeq2)); a <- commandArgs(TRUE)
      raw <- read.delim(a[1], check.names=FALSE); m <- read.delim(a[2]); rownames(m) <- m$sample
      m$condition <- factor(m$condition, levels=c("a","b")); cts <- as.matrix(raw[,-1]); rownames(cts)<-raw[[1]]
      d <- DESeqDataSetFromMatrix(cts,m,~condition); d <- d[rowSums(counts(d)>=10)>=4,]; d <- DESeq(d)
      expected <- as.data.frame(results(d,contrast=c("condition","b","a")))
      actual <- read.delim(a[3]); actual <- actual[match(rownames(expected),actual$gene),]
      stopifnot(isTRUE(all.equal(expected$log2FoldChange,actual$log2FoldChange,tolerance=1e-7)),
                isTRUE(all.equal(expected$padj,actual$padj,tolerance=1e-7)))
      saved <- readRDS(a[4]); coordinates <- plotPCA(saved$vsd,intgroup="condition",returnData=TRUE)
      plotted <- read.delim(a[5]); plotted <- plotted[match(rownames(coordinates),plotted$sample),]
      stopifnot(isTRUE(all.equal(coordinates$PC1,plotted$PC1,tolerance=1e-7)))
    ''', counts, metadata, out / "deseq2_all_results.tsv", checkpoint, qc / "pca_coordinates.tsv")


def test_salmon_offsets_and_statistics_match_direct_tximport(tmp_path):
    _, metadata, values = inputs(tmp_path)
    manifest = tmp_path / "quantfiles.tsv"; mapping = tmp_path / "tx2gene.tsv"
    mapping.write_text("transcript\tgene\n" + "".join(f"tx{i}\tgene{i}\n" for i in range(len(values))))
    rows = []
    for sample in range(8):
        path = tmp_path / f"s{sample}.sf"
        with path.open("w") as handle:
            writer = csv.writer(handle, delimiter="\t")
            writer.writerow(["Name", "Length", "EffectiveLength", "TPM", "NumReads"])
            for gene in range(len(values)):
                writer.writerow([f"tx{gene}", 1000 + gene, 800 + gene + (sample * gene % 90), 1000., float(values[gene, sample]) + .25])
        rows.append(f"s{sample}\t{path}\n")
    manifest.write_text("sample\tquant_file\n" + "".join(rows))
    out = tmp_path / "salmon"; out.mkdir()
    params = ExpressionParameters(reference_level="a", test_level="b", min_samples=4)
    summary = _run_r(manifest, metadata, out, params, input_kind="salmon", tx2gene_path=mapping)
    validate_artifacts(out, summary, "full")
    assert summary["normalization_method"] == "tximport_length_offsets"
    assert (out / "normalization_factors.tsv").exists()
    run_direct('''suppressPackageStartupMessages({library(tximport);library(DESeq2)})
      a <- commandArgs(TRUE); q <- read.delim(a[1]); m <- read.delim(a[2]); rownames(m)<-m$sample
      m$condition <- factor(m$condition,levels=c("a","b")); map <- read.delim(a[3])
      txi <- tximport(setNames(q$quant_file,q$sample), type="salmon",tx2gene=map,countsFromAbundance="no")
      d <- DESeqDataSetFromTximport(txi,m,~condition); d <- d[rowSums(counts(d)>=10)>=4,]; d <- DESeq(d)
      actual <- readRDS(a[4]); stopifnot(isTRUE(all.equal(normalizationFactors(d),normalizationFactors(actual),tolerance=1e-7)))
      expected <- results(d,contrast=c("condition","b","a")); observed <- results(actual,contrast=c("condition","b","a"))
      stopifnot(isTRUE(all.equal(expected$log2FoldChange,observed$log2FoldChange,tolerance=1e-7)),
                isTRUE(all.equal(expected$padj,observed$padj,tolerance=1e-7)))
    ''', manifest, metadata, mapping, out / "dds_fitted.rds")
