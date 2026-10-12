"""Allele semantics and assay-routing regressions from the supplied NGS lectures."""
import math

import pytest

from app.ngs.assays import AssayType, detect_assay
from app.ngs.orchestrator import build_dag
from app.ngs.stages.stage12_normalize import normalize_variants
from app.ngs.stages.stage13_variant_qc import variant_qc
from app.ngs.visualization import variants_to_vcf


@pytest.mark.parametrize("ref,alts", [("GT", "G"), ("G", "GT"), ("GAA", "GAT"), ("GAA", "GAT,GAC"), ("GAT", "GCT")])
def test_minimal_representation_preserves_each_haplotype_and_allele_order(ref, alts):
    genome = "CC" + ref + "TGG"
    original = {"chrom": "chr1", "pos": 3, "ref": ref, "alt": alts, "gt": "1/2", "ad": [8, 5, 3]}
    normalized = normalize_variants([original])[0]
    assert normalized["gt"] == original["gt"]
    assert normalized["ad"] == original["ad"]
    assert normalized["normalization"]["reference_left_aligned"] is False
    assert normalized["ref"]
    for before, after in zip(alts.split(","), normalized["alt"].split(","), strict=True):
        start = normalized["pos"] - 1
        assert after
        assert genome[:2] + before + genome[2 + len(ref):] == genome[:start] + after + genome[start + len(normalized["ref"]):]
    assert normalize_variants([normalized])[0] == normalized
    assert original["ref"] == ref


@pytest.mark.parametrize("bad", [{"pos": 0, "ref": "A", "alt": "C"}, {"pos": 1, "ref": "A", "alt": ""}, {"pos": 1, "ref": "A", "alt": "A"}, {"pos": 1, "ref": "A", "alt": "C,C"}, {"pos": 1, "ref": "A", "alt": "<DEL>"}])
def test_unsupported_records_are_retained_and_fail_qc(bad):
    normalized = normalize_variants([bad])[0]
    assert normalized["ref"] == bad["ref"] and normalized["alt"] == bad["alt"]
    assert normalized["normalization_issue"]
    assert variant_qc({**normalized, "dp": 30, "af": 0.5, "genotype_quality": 99})["status"] == "FAIL"


def test_missing_gq_is_not_maximal_confidence_and_nonfinite_gq_is_not_exported():
    call = {"dp": 30, "af": 0.5, "n_alt": 15}
    qc = variant_qc(call)
    assert qc["status"] == "WARN"
    assert qc["genotype_quality"] is None
    assert "genotype_quality_not_evaluated" in qc["reasons_warn"]
    for invalid in (math.nan, math.inf, -1, "99", True):
        qc = variant_qc({**call, "genotype_quality": invalid})
        assert qc["status"] == "FAIL" and qc["genotype_quality"] is None


def test_vcf_site_quality_read_fraction_and_concordance_have_distinct_meanings():
    calls = [{"chrom": "chr1", "pos": 3, "ref": "A", "alt": "C", "af": 0.25, "genotype_quality": 99, "concordant": True},
             {"chrom": "chr1", "pos": 4, "ref": "A", "alt": "C,T", "af": 0.25, "qual": 40}]
    rows = [r.split("\t") for r in variants_to_vcf(calls).splitlines() if not r.startswith("#")]
    assert rows[0][5:7] == [".", "."]
    assert "VAF=0.25" in rows[0][7] and "OBSERVED_GQ=99" in rows[0][7]
    assert rows[1][5] == "40" and "VAF=" not in rows[1][7]


@pytest.mark.parametrize("assay", ["small-rna-seq", "Small RNA", "miRNA-Seq", "microRNA", "smrnaseq"])
def test_declared_small_rna_never_falls_back_to_bulk_or_dna(assay):
    detected = detect_assay(metadata={"assay": assay})
    assert detected.assay == AssayType.SMALL_RNA_SEQ
    with pytest.raises(ValueError, match="dedicated workflow"):
        build_dag(assay)


def test_small_rna_filename_precedes_generic_rna_hint():
    assert detect_assay(files=["sample_miRNA_R1.fastq.gz"], reference="human_rna").assay == AssayType.SMALL_RNA_SEQ
    assert detect_assay(metadata={"assay": "RNA-seq", "library_strategy": "miRNA-Seq"}).assay == AssayType.SMALL_RNA_SEQ
    assert detect_assay(metadata={"assay": "RNA-seq"}).assay == AssayType.RNA_SEQ


def test_api_returns_actionable_small_rna_guidance():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.routers.ngs_v2 import router
    app = FastAPI()
    app.include_router(router)
    with TestClient(app) as client:
        response = client.post("/api/ngs/v2/analyze", json={"demo_profile": "wgs-clean", "assay": "miRNA-Seq"})
    assert response.status_code == 422
    assert "adapter/UMI" in response.json()["detail"]
