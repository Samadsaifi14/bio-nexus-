"""BioNexus Benchmark Suite 2 (BBS-2) registry and AI fidelity evaluators.

BBS-2 is intentionally explicit about what is *defined*, what has a curated
fixture, and what has been executed.  Merely appearing in the registry never
counts as a passed benchmark.  This prevents benchmark-coverage inflation.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, asdict
from typing import Any


@dataclass(frozen=True)
class BenchmarkSpec:
    id: str
    domain: str
    task: str
    primary_metric: str
    direction: str
    acceptance: str
    fixture_required: bool = True
    status: str = "defined"


SPECS = [
    BenchmarkSpec("SEQ-PAIRWISE", "sequence", "pairwise_alignment", "alignment_score_fidelity", "higher", "matches trusted reference within declared tolerance"),
    BenchmarkSpec("SEQ-BLAST", "sequence", "blast", "top_hit_recall", "higher", "expected reference accession recovered"),
    BenchmarkSpec("SEQ-HMMER", "sequence", "hmmer", "domain_recall", "higher", "curated Pfam domains recovered"),
    BenchmarkSpec("SEQ-PSIBLAST", "sequence", "psi_blast", "homolog_recall", "higher", "known remote homologs recovered"),
    BenchmarkSpec("SEQ-MSA", "sequence", "msa", "sp_score", "higher", "compared with curated alignment"),
    BenchmarkSpec("SEQ-MOTIF", "sequence", "motif_detection", "motif_recall", "higher", "known motifs recovered at controlled FDR"),
    BenchmarkSpec("ANN-UNIPROT", "annotation", "uniprot", "field_fidelity", "higher", "accession/name/gene fields agree with pinned release"),
    BenchmarkSpec("ANN-INTERPRO", "annotation", "interpro", "domain_f1", "higher", "domain calls agree with pinned release"),
    BenchmarkSpec("ANN-GO", "annotation", "go", "term_f1", "higher", "GO terms agree with pinned evidence set"),
    BenchmarkSpec("ANN-REACTOME", "annotation", "reactome", "pathway_recall", "higher", "curated pathways recovered"),
    BenchmarkSpec("ANN-KEGG", "annotation", "kegg", "pathway_recall", "higher", "curated pathways recovered"),
    BenchmarkSpec("ANN-PFAM", "annotation", "pfam", "domain_f1", "higher", "Pfam domains agree with pinned release"),
    BenchmarkSpec("STR-PDB", "structure", "pdb_retrieval", "identifier_fidelity", "higher", "expected structures and metadata recovered"),
    BenchmarkSpec("STR-AF", "structure", "alphafold", "structure_availability_fidelity", "higher", "pinned AlphaFold record reproduced"),
    BenchmarkSpec("STR-DSSP", "structure", "dssp", "secondary_structure_agreement", "higher", "residue assignments agree with DSSP reference"),
    BenchmarkSpec("STR-POCKET", "structure", "pocket_detection", "pocket_overlap", "higher", "known ligand pocket recovered"),
    BenchmarkSpec("STR-SURFACE", "structure", "surface_calculation", "surface_area_error", "lower", "SASA agrees with trusted implementation within tolerance"),
    BenchmarkSpec("DOCK-REDOCK", "docking", "redocking", "pose_rmsd_angstrom", "lower", "heavy-atom RMSD <= 2.0 Å for accepted cases"),
    BenchmarkSpec("DOCK-CROSS", "docking", "cross_docking", "success_rate", "higher", "predeclared target-set success rate"),
    BenchmarkSpec("DOCK-RMSD", "docking", "pose_rmsd", "pose_rmsd_angstrom", "lower", "symmetry-aware RMSD against reference ligand"),
    BenchmarkSpec("DOCK-CLUSTER", "docking", "pose_clustering", "cluster_stability", "higher", "cluster assignments stable under declared seed"),
    BenchmarkSpec("DOCK-AFFINITY", "docking", "binding_affinity", "rank_correlation", "higher", "rank correlation against measured affinity set"),
    *[BenchmarkSpec(f"MD-{name.upper().replace('_','-')}", "md", name, metric, direction, acceptance)
      for name, metric, direction, acceptance in [
        ("rmsd", "series_fidelity", "higher", "series agrees with reference trajectory analysis"),
        ("rmsf", "series_fidelity", "higher", "per-residue series agrees with reference"),
        ("sasa", "series_fidelity", "higher", "SASA series agrees within tolerance"),
        ("radius_of_gyration", "series_fidelity", "higher", "Rg series agrees within tolerance"),
        ("pca", "subspace_overlap", "higher", "leading eigenspace agrees with reference"),
        ("dccm", "matrix_correlation", "higher", "DCCM agrees with reference"),
        ("free_energy", "landscape_similarity", "higher", "declared landscape bins agree with reference"),
      ]],
    *[BenchmarkSpec(f"NGS-{name.upper().replace('_','-')}", "ngs", name, metric, direction, acceptance)
      for name, metric, direction, acceptance in [
        ("fastq_qc", "qc_metric_fidelity", "higher", "FastQC-compatible metrics reproduce pinned fixture"),
        ("alignment", "mapping_metric_fidelity", "higher", "mapping counts and checksums reproduce fixture"),
        ("variant_calling", "variant_f1", "higher", "precision/recall against truth VCF"),
        ("annotation", "annotation_fidelity", "higher", "consequence annotations reproduce pinned release"),
        ("rna_seq", "expression_correlation", "higher", "quantification agrees with trusted reference"),
        ("cnv", "segment_f1", "higher", "CNV segments agree with truth set"),
        ("structural_variants", "sv_f1", "higher", "SV precision/recall against truth set"),
      ]],
    BenchmarkSpec("AI-HALLUCINATION", "ai", "hallucination", "unsupported_claim_rate", "lower", "zero unsupported factual/numeric claims on deterministic fixtures"),
    BenchmarkSpec("AI-NUMERIC", "ai", "numeric_fidelity", "numeric_fidelity", "higher", "every reported number is present in or derivable from evidence"),
    BenchmarkSpec("AI-CITATION", "ai", "citation_fidelity", "citation_fidelity", "higher", "every citation identifier resolves to supplied evidence"),
    BenchmarkSpec("AI-BIOLOGY", "ai", "biological_correctness", "expert_score", "higher", "predeclared expert-reviewed answer key"),
    BenchmarkSpec("AI-UNSUPPORTED", "ai", "unsupported_claim_rate", "unsupported_claim_rate", "lower", "unsupported claim rate = 0 for audited mode"),
]


def registry() -> dict[str, Any]:
    domains: dict[str, int] = {}
    for spec in SPECS:
        domains[spec.domain] = domains.get(spec.domain, 0) + 1
    return {
        "suite": "BBS-2",
        "version": 2,
        "benchmark_count": len(SPECS),
        "domains": domains,
        "benchmarks": [asdict(s) for s in SPECS],
        "semantics": "defined != executed != passed",
    }


def _numbers(text: str) -> list[str]:
    return re.findall(r"(?<![A-Za-z])[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?%?", text or "")


def numeric_fidelity(generated_text: str, evidence_text: str) -> dict:
    generated = _numbers(generated_text)
    evidence = set(_numbers(evidence_text))
    unsupported = [n for n in generated if n not in evidence]
    supported = len(generated) - len(unsupported)
    return {
        "generated_numeric_claims": len(generated),
        "supported_numeric_claims": supported,
        "unsupported_numeric_claims": unsupported,
        "numeric_fidelity": 1.0 if not generated else supported / len(generated),
        "passed": not unsupported,
    }


def citation_fidelity(generated_citations: list[str], allowed_citations: list[str]) -> dict:
    allowed = {c.strip().lower() for c in allowed_citations if c and c.strip()}
    generated = [c.strip() for c in generated_citations if c and c.strip()]
    invalid = [c for c in generated if c.lower() not in allowed]
    valid = len(generated) - len(invalid)
    return {
        "generated_citations": len(generated),
        "valid_citations": valid,
        "invalid_citations": invalid,
        "citation_fidelity": 1.0 if not generated else valid / len(generated),
        "passed": not invalid,
    }


def unsupported_claim_rate(claims: list[dict]) -> dict:
    total = len(claims)
    unsupported_ids: list[str] = []
    for idx, claim in enumerate(claims):
        refs = claim.get("evidence_refs") or claim.get("supporting_computation") or []
        classification = str(claim.get("evidence_class") or claim.get("classification") or "").lower()
        if not refs or "unsupported" in classification or "insufficient" in classification:
            unsupported_ids.append(str(claim.get("id") or idx))
    rate = 0.0 if total == 0 else len(unsupported_ids) / total
    return {"claims": total, "unsupported": len(unsupported_ids), "unsupported_ids": unsupported_ids, "unsupported_claim_rate": rate, "passed": rate == 0.0}


def evaluate_ai_bundle(generated_text: str, evidence_text: str, generated_citations: list[str], allowed_citations: list[str], claims: list[dict]) -> dict:
    numeric = numeric_fidelity(generated_text, evidence_text)
    citations = citation_fidelity(generated_citations, allowed_citations)
    unsupported = unsupported_claim_rate(claims)
    return {
        "numeric": numeric,
        "citations": citations,
        "unsupported_claims": unsupported,
        "passed": numeric["passed"] and citations["passed"] and unsupported["passed"],
    }
