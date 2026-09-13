"""Cross-domain scientific reference comparison for BioNexus.

This module compares a BioNexus result with an independently supplied reference
result using analysis-specific metrics. It never manufactures missing values and
never converts concordance into a claim of platform superiority.

Reference payloads may come from official/accepted tools (for example NCBI
BLAST, EMBL-EBI Clustal Omega, Primer3, Reactome, RCSB PDB, AutoDock Vina,
OpenMM/MDAnalysis, DESeq2/nf-core or GIAB/hap.py). The caller is responsible
for preserving the reference tool/version and the exact input/parameter match.
"""
from __future__ import annotations

from hashlib import sha256
from io import StringIO
import math
from statistics import mean
from typing import Any, Callable


COMPARATOR_REGISTRY: dict[str, dict[str, Any]] = {
    "blast": {
        "reference": "NCBI BLAST (same program/database/parameters)",
        "reference_url": "https://blast.ncbi.nlm.nih.gov/Blast.cgi",
        "kind": "ranked_hit_concordance",
        "metrics": ["top-hit agreement", "top-N accession overlap", "identity correlation", "coverage correlation", "bit-score correlation", "E-value rank profile"],
        "plots": ["identity_vs_coverage_scatter", "negative_log10_evalue_by_rank", "bit_score_by_rank", "rank_concordance"],
    },
    "pairwise": {
        "reference": "EMBOSS Needle/Water or another declared pairwise implementation",
        "reference_url": "https://www.ebi.ac.uk/Tools/psa/",
        "kind": "alignment_metric_concordance",
        "metrics": ["alignment score", "identity", "aligned length", "gap count"],
        "plots": ["metric_delta", "dot_plot"],
    },
    "msa": {
        "reference": "EMBL-EBI Clustal Omega (same sequences/parameters)",
        "reference_url": "https://www.ebi.ac.uk/Tools/msa/clustalo/",
        "kind": "alignment_concordance",
        "metrics": ["aligned sequence set", "alignment length", "normalized alignment SHA-256", "mean pairwise identity", "conservation correlation"],
        "plots": ["conservation_profile", "entropy_profile", "pairwise_identity_matrix"],
    },
    "phylo": {
        "reference": "IQ-TREE 2 / declared phylogenetic reference implementation",
        "reference_url": "https://iqtree.github.io/",
        "kind": "tree_topology_concordance",
        "metrics": ["leaf-set agreement", "split-set Jaccard", "Robinson-Foulds-like split distance"],
        "plots": ["support_distribution", "branch_length_distribution", "topology_concordance"],
    },
    "primers": {
        "reference": "Primer3",
        "reference_url": "https://primer3.org/",
        "kind": "primer_candidate_concordance",
        "metrics": ["primer sequence match", "position match", "Tm delta", "GC delta", "product-size delta"],
        "plots": ["primer_tm", "primer_gc", "product_size", "penalty"],
    },
    "domains": {
        "reference": "InterPro / InterProScan",
        "reference_url": "https://www.ebi.ac.uk/interpro/",
        "kind": "feature_interval_concordance",
        "metrics": ["signature overlap", "coordinate agreement", "feature coverage"],
        "plots": ["domain_architecture", "feature_overlap"],
    },
    "motif": {
        "reference": "PROSITE / InterPro",
        "reference_url": "https://prosite.expasy.org/",
        "kind": "feature_interval_concordance",
        "metrics": ["signature overlap", "coordinate agreement"],
        "plots": ["motif_track", "feature_overlap"],
    },
    "pathway": {
        "reference": "Reactome Analysis Service",
        "reference_url": "https://reactome.org/PathwayBrowser/#TOOL=AT",
        "kind": "enrichment_concordance",
        "metrics": ["stable-ID overlap", "FDR correlation", "gene-ratio correlation"],
        "plots": ["gene_ratio_vs_negative_log10_fdr", "top_pathway_fdr", "pathway_overlap"],
    },
    "uniprot": {
        "reference": "UniProtKB REST",
        "reference_url": "https://www.uniprot.org/",
        "kind": "reference_record_concordance",
        "metrics": ["accession agreement", "reviewed status", "GO/EC overlap", "feature overlap"],
        "plots": ["annotation_overlap"],
    },
    "function": {
        "reference": "InterPro2GO / reviewed UniProtKB annotation",
        "reference_url": "https://www.ebi.ac.uk/interpro/",
        "kind": "annotation_set_concordance",
        "metrics": ["GO-term overlap", "namespace overlap", "EC overlap when available"],
        "plots": ["go_namespace_counts", "go_overlap"],
    },
    "interactions": {
        "reference": "STRING database (same species/version)",
        "reference_url": "https://string-db.org/",
        "kind": "interaction_set_concordance",
        "metrics": ["partner overlap", "combined-score correlation"],
        "plots": ["interaction_score_scatter", "partner_overlap"],
    },
    "structure": {
        "reference": "RCSB PDB / AlphaFold DB plus declared structural reference tool",
        "reference_url": "https://www.rcsb.org/",
        "kind": "structure_record_concordance",
        "metrics": ["coordinate checksum when retrieving the same record", "residue count", "quality-metric deltas"],
        "plots": ["ramachandran", "secondary_structure", "confidence_profile", "quality_metric_delta"],
    },
    "castp": {
        "reference": "CASTp",
        "reference_url": "https://sts.bioe.uic.edu/castp/",
        "kind": "pocket_concordance",
        "metrics": ["pocket residue overlap", "volume delta", "area delta"],
        "plots": ["pocket_volume", "pocket_area", "residue_overlap"],
    },
    "docking": {
        "reference": "AutoDock Vina standalone plus crystallographic redocking when a truth pose exists",
        "reference_url": "https://autodock-vina.readthedocs.io/",
        "kind": "pose_score_concordance",
        "metrics": ["best affinity delta", "pose-score correlation", "redocking RMSD when available"],
        "plots": ["affinity_by_pose", "rmsd_bounds_by_pose", "redocking_rmsd"],
    },
    "md": {
        "reference": "OpenMM reference run and independent trajectory analysis (for example MDAnalysis/CPPTRAJ)",
        "reference_url": "https://openmm.org/",
        "kind": "trajectory_metric_concordance",
        "metrics": ["RMSD correlation/RMSE", "RMSF correlation/RMSE", "Rg correlation/RMSE", "SASA correlation/RMSE", "H-bond correlation/RMSE"],
        "plots": ["rmsd_time", "rmsf_residue", "radius_of_gyration_time", "sasa_time", "hbond_time", "pca", "dccm"],
    },
    "admet": {
        "reference": "RDKit for deterministic descriptors; declared validated model for predictive endpoints",
        "reference_url": "https://www.rdkit.org/",
        "kind": "descriptor_concordance",
        "metrics": ["descriptor absolute/relative delta", "rule calculation agreement"],
        "plots": ["descriptor_delta", "property_space"],
    },
    "ngs": {
        "reference": "nf-core/sarek plus GIAB/GA4GH truth benchmarking with hap.py",
        "reference_url": "https://www.nist.gov/programs-projects/genome-bottle",
        "kind": "truth_set_benchmark",
        "metrics": ["TP", "FP", "FN", "precision", "recall", "F1", "stratified performance"],
        "plots": ["precision_recall", "variant_type_counts", "coverage", "stratified_accuracy"],
    },
    "rnaseq": {
        "reference": "nf-core/rnaseq plus R/Bioconductor DESeq2",
        "reference_url": "https://bioconductor.org/packages/DESeq2",
        "kind": "differential_expression_concordance",
        "metrics": ["log2-fold-change correlation", "adjusted-P concordance", "significant-gene overlap", "direction concordance"],
        "plots": ["volcano", "ma", "pca", "sample_distance_heatmap", "log2fc_reference_scatter", "significant_gene_overlap"],
    },
}


def comparator_registry() -> dict[str, Any]:
    return {
        "schema": "bionexus-reference-comparison/v1",
        "policy": "Same input, same reference/database, same parameters and declared acceptance rule. Concordance does not imply superiority.",
        "comparators": COMPARATOR_REGISTRY,
    }


def _f(value: Any) -> float | None:
    try:
        x = float(value)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def _pearson(xs: list[float], ys: list[float]) -> float | None:
    n = min(len(xs), len(ys))
    if n < 2:
        return None
    xs, ys = xs[:n], ys[:n]
    mx, my = mean(xs), mean(ys)
    dx = [x - mx for x in xs]
    dy = [y - my for y in ys]
    denom = math.sqrt(sum(v * v for v in dx) * sum(v * v for v in dy))
    if denom == 0:
        return 1.0 if xs == ys else None
    return sum(a * b for a, b in zip(dx, dy)) / denom


def _rmse(xs: list[float], ys: list[float]) -> float | None:
    n = min(len(xs), len(ys))
    if n == 0:
        return None
    return math.sqrt(sum((xs[i] - ys[i]) ** 2 for i in range(n)) / n)


def _jaccard(a: set[str], b: set[str]) -> float | None:
    union = a | b
    return len(a & b) / len(union) if union else None


def _neglog10(value: Any) -> float | None:
    x = _f(value)
    if x is None or x < 0:
        return None
    if x == 0:
        return 300.0
    return min(300.0, -math.log10(x))


def _status(score: float | None) -> str:
    if score is None:
        return "INSUFFICIENT_EVIDENCE"
    if score >= 0.999:
        return "EXACT_OR_NEAR_EXACT_CONCORDANCE"
    if score >= 0.90:
        return "HIGH_CONCORDANCE"
    if score >= 0.60:
        return "PARTIAL_CONCORDANCE"
    return "LOW_CONCORDANCE"


def _metric(id_: str, label: str, value: Any, *, reference: Any = None, unit: str | None = None, note: str | None = None) -> dict[str, Any]:
    return {"id": id_, "label": label, "value": value, "reference_value": reference, "unit": unit, "note": note}


def _normalise_accession(value: Any) -> str:
    text = str(value or "").strip()
    return text.split(".")[0].upper()


def _hits(payload: dict[str, Any]) -> list[dict[str, Any]]:
    raw = payload.get("hits") or payload.get("results") or payload.get("blast", {}).get("hits") or []
    return [x for x in raw if isinstance(x, dict)]


def _compare_blast(b: dict[str, Any], r: dict[str, Any], top_n: int) -> dict[str, Any]:
    bh = _hits(b)[:top_n]
    rh = _hits(r)[:top_n]
    bmap = {_normalise_accession(x.get("accession")): x for x in bh if _normalise_accession(x.get("accession"))}
    rmap = {_normalise_accession(x.get("accession")): x for x in rh if _normalise_accession(x.get("accession"))}
    common = [acc for acc in bmap if acc in rmap]
    overlap = _jaccard(set(bmap), set(rmap))
    top_hit_same = bool(bh and rh and _normalise_accession(bh[0].get("accession")) == _normalise_accession(rh[0].get("accession")))

    def paired(field: str, transform: Callable[[Any], float | None] = _f) -> tuple[list[float], list[float]]:
        xs: list[float] = []
        ys: list[float] = []
        for acc in common:
            x, y = transform(bmap[acc].get(field)), transform(rmap[acc].get(field))
            if x is not None and y is not None:
                xs.append(x); ys.append(y)
        return xs, ys

    identity_b, identity_r = paired("identity_pct")
    cov_b, cov_r = paired("query_coverage_pct")
    bit_b, bit_r = paired("bit_score")
    ev_b, ev_r = paired("evalue", _neglog10)
    correlations = [_pearson(*pair) for pair in [(identity_b, identity_r), (cov_b, cov_r), (bit_b, bit_r), (ev_b, ev_r)]]
    corr_vals = [x for x in correlations if x is not None]
    agreement_score = mean(([1.0 if top_hit_same else 0.0, overlap or 0.0] + [max(-1.0, min(1.0, x)) * 0.5 + 0.5 for x in corr_vals])) if (bh or rh) else None

    def rank_series(hits: list[dict[str, Any]], source: str) -> list[dict[str, Any]]:
        out = []
        for i, hit in enumerate(hits, 1):
            out.append({
                "rank": i,
                "source": source,
                "accession": hit.get("accession"),
                "neglog10_evalue": _neglog10(hit.get("evalue")),
                "identity_pct": _f(hit.get("identity_pct")),
                "coverage_pct": _f(hit.get("query_coverage_pct")),
                "bit_score": _f(hit.get("bit_score")),
            })
        return out

    return {
        "metrics": [
            _metric("top_hit_agreement", "Top-hit accession agreement", top_hit_same),
            _metric("top_n_jaccard", f"Top-{top_n} accession Jaccard", overlap),
            _metric("common_hits", "Common accessions", len(common), unit="hits"),
            _metric("identity_correlation", "Identity correlation", _pearson(identity_b, identity_r)),
            _metric("coverage_correlation", "Query-coverage correlation", _pearson(cov_b, cov_r)),
            _metric("bit_score_correlation", "Bit-score correlation", _pearson(bit_b, bit_r)),
            _metric("evalue_profile_correlation", "-log10(E-value) correlation", _pearson(ev_b, ev_r)),
        ],
        "series": [{"id": "blast_rank_profile", "kind": "blast_rank_profile", "points": rank_series(bh, "BioNexus") + rank_series(rh, "Reference")}],
        "agreement_score": agreement_score,
        "matched_entities": common,
    }


def _parse_fasta_alignment(text: str) -> dict[str, str]:
    records: dict[str, str] = {}
    key: str | None = None
    parts: list[str] = []
    for raw in str(text or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith(">"):
            if key is not None:
                records[key] = "".join(parts).upper()
            key = line[1:].split()[0]
            parts = []
        elif key is not None:
            parts.append(line.replace(" ", ""))
    if key is not None:
        records[key] = "".join(parts).upper()
    return records


def _alignment_digest(records: dict[str, str]) -> str:
    payload = "\n".join(f">{k}\n{records[k]}" for k in sorted(records))
    return sha256(payload.encode("utf-8")).hexdigest()


def _pair_identity(a: str, b: str) -> float | None:
    n = min(len(a), len(b))
    comparable = [(a[i], b[i]) for i in range(n) if a[i] not in "-." and b[i] not in "-."]
    if not comparable:
        return None
    return sum(1 for x, y in comparable if x == y) / len(comparable)


def _conservation(records: dict[str, str]) -> list[float]:
    if not records:
        return []
    seqs = list(records.values())
    length = min(map(len, seqs))
    out = []
    for i in range(length):
        col = [s[i] for s in seqs if s[i] not in "-."]
        if not col:
            out.append(0.0); continue
        counts: dict[str, int] = {}
        for c in col:
            counts[c] = counts.get(c, 0) + 1
        out.append(max(counts.values()) / len(col))
    return out


def _compare_msa(b: dict[str, Any], r: dict[str, Any], _top_n: int) -> dict[str, Any]:
    br = _parse_fasta_alignment(str(b.get("aln_fasta") or b.get("alignment") or ""))
    rr = _parse_fasta_alignment(str(r.get("aln_fasta") or r.get("alignment") or ""))
    common = sorted(set(br) & set(rr))
    bd, rd = _alignment_digest(br) if br else None, _alignment_digest(rr) if rr else None
    b_ids: list[float] = []
    r_ids: list[float] = []
    for i, a in enumerate(common):
        for c in common[i + 1:]:
            x, y = _pair_identity(br[a], br[c]), _pair_identity(rr[a], rr[c])
            if x is not None and y is not None:
                b_ids.append(x); r_ids.append(y)
    bc, rc = _conservation({k: br[k] for k in common}), _conservation({k: rr[k] for k in common})
    conserved_corr = _pearson(bc, rc) if len(bc) == len(rc) else None
    seq_overlap = _jaccard(set(br), set(rr))
    exact = bool(bd and rd and bd == rd)
    scores = [1.0 if exact else 0.0]
    if seq_overlap is not None: scores.append(seq_overlap)
    pic = _pearson(b_ids, r_ids)
    if pic is not None: scores.append((pic + 1) / 2)
    if conserved_corr is not None: scores.append((conserved_corr + 1) / 2)
    return {
        "metrics": [
            _metric("sequence_set_jaccard", "Aligned sequence-set Jaccard", seq_overlap),
            _metric("alignment_sha256_match", "Normalized alignment SHA-256 match", exact, reference=rd),
            _metric("bionexus_alignment_sha256", "BioNexus alignment SHA-256", bd),
            _metric("pairwise_identity_correlation", "Pairwise-identity correlation", pic),
            _metric("conservation_correlation", "Per-column conservation correlation", conserved_corr),
        ],
        "series": [{
            "id": "conservation_profile",
            "kind": "paired_line",
            "points": [
                *[{"x": i + 1, "y": y, "source": "BioNexus"} for i, y in enumerate(bc)],
                *[{"x": i + 1, "y": y, "source": "Reference"} for i, y in enumerate(rc)],
            ],
            "x_label": "Alignment column",
            "y_label": "Conservation fraction",
        }],
        "agreement_score": mean(scores) if scores else None,
        "matched_entities": common,
    }


def _primer_pairs(payload: dict[str, Any]) -> list[dict[str, Any]]:
    raw = payload.get("pairs") or payload.get("results") or payload.get("primers") or payload if isinstance(payload, list) else payload.get("pairs", [])
    return [x for x in raw if isinstance(x, dict)] if isinstance(raw, list) else []


def _compare_primers(b: dict[str, Any], r: dict[str, Any], top_n: int) -> dict[str, Any]:
    bp, rp = _primer_pairs(b)[:top_n], _primer_pairs(r)[:top_n]
    n = min(len(bp), len(rp))
    exact_pairs = 0
    tm_delta: list[float] = []
    gc_delta: list[float] = []
    product_delta: list[float] = []
    points: list[dict[str, Any]] = []
    for i in range(n):
        x, y = bp[i], rp[i]
        bleft = str(x.get("left_seq") or x.get("left_sequence") or "").upper()
        bright = str(x.get("right_seq") or x.get("right_sequence") or "").upper()
        rleft = str(y.get("left_seq") or y.get("left_sequence") or "").upper()
        rright = str(y.get("right_seq") or y.get("right_sequence") or "").upper()
        exact_pairs += int(bool(bleft and bright and bleft == rleft and bright == rright))
        for field, dest in [("left_tm", tm_delta), ("right_tm", tm_delta)]:
            a, z = _f(x.get(field)), _f(y.get(field))
            if a is not None and z is not None: dest.append(abs(a-z))
        for field, dest in [("left_gc", gc_delta), ("right_gc", gc_delta)]:
            a, z = _f(x.get(field)), _f(y.get(field))
            if a is not None and z is not None: dest.append(abs(a-z))
        a, z = _f(x.get("product_size")), _f(y.get("product_size"))
        if a is not None and z is not None: product_delta.append(abs(a-z))
        points.append({"pair": i + 1, "bionexus_tm": _f(x.get("left_tm")), "reference_tm": _f(y.get("left_tm")), "bionexus_gc": _f(x.get("left_gc")), "reference_gc": _f(y.get("left_gc"))})
    exact_frac = exact_pairs / n if n else None
    delta_scores = []
    if tm_delta: delta_scores.append(max(0.0, 1.0 - mean(tm_delta) / 5.0))
    if gc_delta: delta_scores.append(max(0.0, 1.0 - mean(gc_delta) / 20.0))
    if product_delta: delta_scores.append(max(0.0, 1.0 - mean(product_delta) / 100.0))
    return {
        "metrics": [
            _metric("exact_pair_fraction", "Exact primer-pair sequence fraction", exact_frac),
            _metric("mean_tm_abs_delta", "Mean Tm absolute delta", mean(tm_delta) if tm_delta else None, unit="°C"),
            _metric("mean_gc_abs_delta", "Mean GC absolute delta", mean(gc_delta) if gc_delta else None, unit="percentage points"),
            _metric("mean_product_size_abs_delta", "Mean product-size absolute delta", mean(product_delta) if product_delta else None, unit="bp"),
        ],
        "series": [{"id": "primer_pair_metrics", "kind": "primer_pair_metrics", "points": points}],
        "agreement_score": mean(([exact_frac] if exact_frac is not None else []) + delta_scores) if ([exact_frac] if exact_frac is not None else []) + delta_scores else None,
    }


def _pathway_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    raw = payload.get("pathways") or payload.get("results") or payload.get("analysis", {}).get("pathways") or []
    return [x for x in raw if isinstance(x, dict)]


def _pathway_id(row: dict[str, Any]) -> str:
    return str(row.get("stId") or row.get("pathway_id") or row.get("id") or "").upper()


def _compare_pathway(b: dict[str, Any], r: dict[str, Any], top_n: int) -> dict[str, Any]:
    bp, rp = _pathway_rows(b)[:top_n], _pathway_rows(r)[:top_n]
    bm = {_pathway_id(x): x for x in bp if _pathway_id(x)}
    rm = {_pathway_id(x): x for x in rp if _pathway_id(x)}
    common = sorted(set(bm) & set(rm))
    overlap = _jaccard(set(bm), set(rm))
    bfdr, rfdr, brat, rrat = [], [], [], []
    for k in common:
        a = _neglog10(bm[k].get("entitiesFDR", bm[k].get("fdr", bm[k].get("padj"))))
        z = _neglog10(rm[k].get("entitiesFDR", rm[k].get("fdr", rm[k].get("padj"))))
        if a is not None and z is not None: bfdr.append(a); rfdr.append(z)
        a = _f(bm[k].get("geneRatio", bm[k].get("gene_ratio")))
        z = _f(rm[k].get("geneRatio", rm[k].get("gene_ratio")))
        if a is not None and z is not None: brat.append(a); rrat.append(z)
    points = []
    for source, rows in [("BioNexus", bp), ("Reference", rp)]:
        for row in rows:
            points.append({"source": source, "id": _pathway_id(row), "name": row.get("name"), "gene_ratio": _f(row.get("geneRatio", row.get("gene_ratio"))), "neglog10_fdr": _neglog10(row.get("entitiesFDR", row.get("fdr", row.get("padj"))))})
    corrs = [x for x in [_pearson(bfdr, rfdr), _pearson(brat, rrat)] if x is not None]
    score_parts = [overlap] if overlap is not None else []
    score_parts += [(x + 1) / 2 for x in corrs]
    return {
        "metrics": [
            _metric("stable_id_jaccard", f"Top-{top_n} pathway stable-ID Jaccard", overlap),
            _metric("fdr_correlation", "-log10(FDR) correlation", _pearson(bfdr, rfdr)),
            _metric("gene_ratio_correlation", "Gene-ratio correlation", _pearson(brat, rrat)),
        ],
        "series": [{"id": "pathway_enrichment_scatter", "kind": "pathway_scatter", "points": points}],
        "agreement_score": mean(score_parts) if score_parts else None,
        "matched_entities": common,
    }


def _compare_rnaseq(b: dict[str, Any], r: dict[str, Any], _top_n: int) -> dict[str, Any]:
    def rows(p: dict[str, Any]) -> list[dict[str, Any]]:
        raw = p.get("results") or p.get("genes") or p.get("deseq2_all_results") or []
        return [x for x in raw if isinstance(x, dict)]
    def gene(row: dict[str, Any]) -> str:
        return str(row.get("gene") or row.get("gene_id") or row.get("id") or "")
    br, rr = rows(b), rows(r)
    bm, rm = {gene(x): x for x in br if gene(x)}, {gene(x): x for x in rr if gene(x)}
    common = sorted(set(bm) & set(rm))
    blfc: list[float] = []; rlfc: list[float] = []; bpadj: list[float] = []; rpadj: list[float] = []
    direction_same = 0; direction_n = 0
    b_sig: set[str] = set(); r_sig: set[str] = set()
    points = []
    for g in common:
        bx, rx = _f(bm[g].get("log2FoldChange", bm[g].get("log2fc"))), _f(rm[g].get("log2FoldChange", rm[g].get("log2fc")))
        bp, rp = _f(bm[g].get("padj")), _f(rm[g].get("padj"))
        if bx is not None and rx is not None:
            blfc.append(bx); rlfc.append(rx); direction_n += 1; direction_same += int((bx >= 0) == (rx >= 0))
            points.append({"gene": g, "bionexus_log2fc": bx, "reference_log2fc": rx, "bionexus_neglog10_padj": _neglog10(bp), "reference_neglog10_padj": _neglog10(rp)})
        if bp is not None and rp is not None:
            nbp, nrp = _neglog10(bp), _neglog10(rp)
            if nbp is not None and nrp is not None: bpadj.append(nbp); rpadj.append(nrp)
        if bp is not None and bp < 0.05: b_sig.add(g)
        if rp is not None and rp < 0.05: r_sig.add(g)
    sig_overlap = _jaccard(b_sig, r_sig)
    lfc_corr, padj_corr = _pearson(blfc, rlfc), _pearson(bpadj, rpadj)
    direction = direction_same / direction_n if direction_n else None
    vals = [x for x in [sig_overlap, direction] if x is not None] + [((x + 1) / 2) for x in [lfc_corr, padj_corr] if x is not None]
    return {
        "metrics": [
            _metric("shared_genes", "Shared genes", len(common), unit="genes"),
            _metric("log2fc_correlation", "log2 fold-change correlation", lfc_corr),
            _metric("padj_correlation", "-log10 adjusted-P correlation", padj_corr),
            _metric("significant_gene_jaccard", "Significant-gene Jaccard (padj < 0.05)", sig_overlap),
            _metric("direction_concordance", "Fold-change direction concordance", direction),
        ],
        "series": [{"id": "rnaseq_log2fc_reference", "kind": "reference_scatter", "points": points, "x_label": "Reference log2FC", "y_label": "BioNexus log2FC"}],
        "agreement_score": mean(vals) if vals else None,
        "matched_entities": common,
    }


def _compare_docking(b: dict[str, Any], r: dict[str, Any], _top_n: int) -> dict[str, Any]:
    def poses(p: dict[str, Any]) -> list[dict[str, Any]]:
        raw = p.get("poses") or p.get("result", {}).get("poses") or []
        return [x for x in raw if isinstance(x, dict)]
    bp, rp = poses(b), poses(r)
    n = min(len(bp), len(rp))
    ba, ra = [], []
    pts = []
    for i in range(n):
        x, y = _f(bp[i].get("affinity")), _f(rp[i].get("affinity"))
        if x is not None and y is not None: ba.append(x); ra.append(y)
        pts.append({"pose": i + 1, "bionexus_affinity": x, "reference_affinity": y, "bionexus_rmsd_lb": _f(bp[i].get("rmsd_lb")), "reference_rmsd_lb": _f(rp[i].get("rmsd_lb"))})
    best_b = min(ba) if ba else None; best_r = min(ra) if ra else None
    corr = _pearson(ba, ra)
    delta = abs(best_b-best_r) if best_b is not None and best_r is not None else None
    redock = _f(b.get("redocking_rmsd", b.get("rmsd_to_crystal")))
    ref_redock = _f(r.get("redocking_rmsd", r.get("rmsd_to_crystal")))
    vals = []
    if corr is not None: vals.append((corr+1)/2)
    if delta is not None: vals.append(max(0.0, 1.0-delta/2.0))
    return {
        "metrics": [
            _metric("best_affinity_delta", "Best-affinity absolute delta", delta, unit="kcal/mol", reference=best_r),
            _metric("pose_affinity_correlation", "Pose-affinity correlation", corr),
            _metric("redocking_rmsd", "BioNexus redocking RMSD", redock, unit="Å", reference=ref_redock, note="Only interpretable when both use the same crystallographic ligand and atom mapping."),
        ],
        "series": [{"id": "docking_pose_scores", "kind": "docking_pose_scores", "points": pts}],
        "agreement_score": mean(vals) if vals else None,
    }


def _series_values(payload: dict[str, Any], key: str) -> list[float]:
    raw = payload.get(key)
    if raw is None and isinstance(payload.get("timeseries"), dict): raw = payload["timeseries"].get(key)
    if raw is None and isinstance(payload.get("result"), dict): raw = payload["result"].get(key)
    if not isinstance(raw, list): return []
    out = []
    for item in raw:
        val = _f(item.get("value") if isinstance(item, dict) else item)
        if val is not None: out.append(val)
    return out


def _compare_md(b: dict[str, Any], r: dict[str, Any], _top_n: int) -> dict[str, Any]:
    metrics = []
    score_parts = []
    series = []
    for key, label, unit in [
        ("rmsd", "RMSD", "Å"), ("rmsf", "RMSF", "Å"), ("radius_of_gyration", "Radius of gyration", "Å"),
        ("rg", "Radius of gyration", "Å"), ("sasa", "SASA", "Å²"), ("hbonds", "Hydrogen bonds", "count"),
    ]:
        bv, rv = _series_values(b, key), _series_values(r, key)
        if not bv and not rv: continue
        corr, err = _pearson(bv, rv), _rmse(bv, rv)
        metrics.append(_metric(f"{key}_correlation", f"{label} correlation", corr))
        metrics.append(_metric(f"{key}_rmse", f"{label} RMSE", err, unit=unit))
        if corr is not None: score_parts.append((corr+1)/2)
        series.append({"id": key, "kind": "paired_line", "x_label": "Frame / index", "y_label": label, "points": [*[{"x": i, "y": v, "source": "BioNexus"} for i, v in enumerate(bv)], *[{"x": i, "y": v, "source": "Reference"} for i, v in enumerate(rv)]]})
    return {"metrics": metrics, "series": series, "agreement_score": mean(score_parts) if score_parts else None}


def _numeric_map(payload: dict[str, Any]) -> dict[str, float]:
    source = payload.get("descriptors") if isinstance(payload.get("descriptors"), dict) else payload.get("metrics") if isinstance(payload.get("metrics"), dict) else payload
    out: dict[str, float] = {}
    if isinstance(source, dict):
        for k, v in source.items():
            x = _f(v)
            if x is not None: out[str(k)] = x
    return out


def _compare_numeric(b: dict[str, Any], r: dict[str, Any], _top_n: int) -> dict[str, Any]:
    bm, rm = _numeric_map(b), _numeric_map(r)
    common = sorted(set(bm) & set(rm))
    points = []
    rel_errors = []
    metrics = []
    for key in common:
        delta = bm[key]-rm[key]
        denom = max(abs(rm[key]), 1e-12)
        rel = abs(delta)/denom
        rel_errors.append(rel)
        points.append({"metric": key, "bionexus": bm[key], "reference": rm[key], "delta": delta, "relative_error": rel})
    mae_rel = mean(rel_errors) if rel_errors else None
    corr = _pearson([bm[k] for k in common], [rm[k] for k in common]) if len(common) >= 2 else None
    metrics.append(_metric("shared_numeric_metrics", "Shared numeric metrics", len(common)))
    metrics.append(_metric("mean_relative_error", "Mean relative error", mae_rel))
    metrics.append(_metric("numeric_correlation", "Numeric metric correlation", corr))
    score = max(0.0, 1.0-mae_rel) if mae_rel is not None else None
    return {"metrics": metrics, "series": [{"id": "numeric_metric_delta", "kind": "metric_delta", "points": points}], "agreement_score": score, "matched_entities": common}


def _annotation_ids(payload: dict[str, Any], keys: tuple[str, ...]) -> set[str]:
    for key in keys:
        raw = payload.get(key)
        if isinstance(raw, list):
            out = set()
            for item in raw:
                if isinstance(item, dict):
                    value = item.get("id") or item.get("accession") or item.get("go_id") or item.get("partner_gene") or item.get("partner_protein")
                else: value = item
                if value: out.add(str(value).upper())
            return out
    return set()


def _compare_sets(b: dict[str, Any], r: dict[str, Any], _top_n: int) -> dict[str, Any]:
    keys = ("go_terms", "features", "domains", "hits", "interactions", "partners", "motifs")
    bs, rs = _annotation_ids(b, keys), _annotation_ids(r, keys)
    overlap = _jaccard(bs, rs)
    return {
        "metrics": [_metric("set_jaccard", "Reference-identifier Jaccard", overlap), _metric("shared_identifiers", "Shared identifiers", len(bs & rs))],
        "series": [{"id": "identifier_overlap", "kind": "set_overlap", "points": [{"group": "BioNexus only", "count": len(bs-rs)}, {"group": "Shared", "count": len(bs&rs)}, {"group": "Reference only", "count": len(rs-bs)}]}],
        "agreement_score": overlap,
        "matched_entities": sorted(bs & rs),
    }


def _compare_interactions(b: dict[str, Any], r: dict[str, Any], top_n: int) -> dict[str, Any]:
    def rows(p: dict[str, Any]) -> list[dict[str, Any]]:
        raw = p.get("interactions") or p.get("partners") or []
        return [x for x in raw if isinstance(x, dict)][:top_n]
    def pid(x: dict[str, Any]) -> str:
        return str(x.get("partner_gene") or x.get("partner_protein") or x.get("id") or "").upper()
    br, rr = rows(b), rows(r)
    bm, rm = {pid(x): x for x in br if pid(x)}, {pid(x): x for x in rr if pid(x)}
    common = sorted(set(bm)&set(rm))
    bx, rx = [], []
    for k in common:
        a, z = _f(bm[k].get("combined_score", bm[k].get("score"))), _f(rm[k].get("combined_score", rm[k].get("score")))
        if a is not None and z is not None: bx.append(a); rx.append(z)
    overlap, corr = _jaccard(set(bm), set(rm)), _pearson(bx, rx)
    vals = ([overlap] if overlap is not None else []) + ([((corr+1)/2)] if corr is not None else [])
    return {
        "metrics": [_metric("partner_jaccard", f"Top-{top_n} partner Jaccard", overlap), _metric("score_correlation", "Combined-score correlation", corr)],
        "series": [{"id": "interaction_overlap", "kind": "set_overlap", "points": [{"group": "BioNexus only", "count": len(set(bm)-set(rm))}, {"group": "Shared", "count": len(common)}, {"group": "Reference only", "count": len(set(rm)-set(bm))}]}],
        "agreement_score": mean(vals) if vals else None,
        "matched_entities": common,
    }


def _tree_splits(newick: str) -> tuple[set[str], set[frozenset[str]]]:
    try:
        from Bio import Phylo  # type: ignore
        tree = Phylo.read(StringIO(newick), "newick")
    except Exception:
        return set(), set()
    leaves = {str(x.name) for x in tree.get_terminals() if x.name}
    splits: set[frozenset[str]] = set()
    for clade in tree.get_nonterminals(order="preorder"):
        subset = frozenset(str(x.name) for x in clade.get_terminals() if x.name)
        if 1 < len(subset) < len(leaves)-1:
            complement = frozenset(leaves-set(subset))
            splits.add(min(subset, complement, key=lambda s: (len(s), sorted(s))))
    return leaves, splits


def _compare_phylo(b: dict[str, Any], r: dict[str, Any], _top_n: int) -> dict[str, Any]:
    bn = str(b.get("newick") or b.get("phylotree_newick") or b.get("phylotree") or "")
    rn = str(r.get("newick") or r.get("phylotree_newick") or r.get("phylotree") or "")
    bl, bs = _tree_splits(bn); rl, rs = _tree_splits(rn)
    leaf_match = bl == rl and bool(bl)
    split_j = _jaccard({"|".join(sorted(x)) for x in bs}, {"|".join(sorted(x)) for x in rs})
    symdiff = len(bs ^ rs) if bs or rs else None
    vals = ([1.0 if leaf_match else 0.0] if (bl or rl) else []) + ([split_j] if split_j is not None else [])
    return {
        "metrics": [_metric("leaf_set_agreement", "Leaf-set agreement", leaf_match), _metric("split_jaccard", "Split-set Jaccard", split_j), _metric("split_symmetric_difference", "Split symmetric difference", symdiff, note="A topology-distance diagnostic; not a support/confidence score.")],
        "series": [],
        "agreement_score": mean(vals) if vals else None,
    }


_COMPARATORS: dict[str, Callable[[dict[str, Any], dict[str, Any], int], dict[str, Any]]] = {
    "blast": _compare_blast,
    "msa": _compare_msa,
    "primers": _compare_primers,
    "pathway": _compare_pathway,
    "rnaseq": _compare_rnaseq,
    "docking": _compare_docking,
    "md": _compare_md,
    "admet": _compare_numeric,
    "ngs": _compare_numeric,
    "pairwise": _compare_numeric,
    "structure": _compare_numeric,
    "castp": _compare_numeric,
    "uniprot": _compare_sets,
    "function": _compare_sets,
    "domains": _compare_sets,
    "motif": _compare_sets,
    "interactions": _compare_interactions,
    "phylo": _compare_phylo,
}


def compare_results(analysis_type: str, bionexus: dict[str, Any], reference: dict[str, Any], *, top_n: int = 10, reference_metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    key = str(analysis_type or "").strip().lower()
    if key not in COMPARATOR_REGISTRY:
        raise ValueError(f"Unsupported analysis_type: {analysis_type}")
    if not isinstance(bionexus, dict) or not isinstance(reference, dict):
        raise ValueError("bionexus and reference must be JSON objects")
    fn = _COMPARATORS.get(key, _compare_numeric)
    result = fn(bionexus, reference, max(1, min(int(top_n or 10), 100)))
    score = result.get("agreement_score")
    return {
        "schema": "bionexus-reference-comparison/v1",
        "analysis_type": key,
        "comparator": COMPARATOR_REGISTRY[key],
        "reference_metadata": reference_metadata or {},
        "concordance": {
            "score": score,
            "status": _status(score),
            "meaning": "Agreement between matched outputs under the supplied comparison contract. It is not a claim that either platform is biologically superior.",
        },
        "metrics": result.get("metrics", []),
        "series": result.get("series", []),
        "matched_entities": result.get("matched_entities", []),
        "claim_boundary": {
            "same_input_required": True,
            "same_reference_or_database_required": True,
            "same_parameters_required": True,
            "missing_measurements_are_not_zero": True,
            "superiority_claim_allowed": False,
            "note": "A superiority claim requires a predeclared benchmark endpoint/truth set and appropriate statistical evaluation, not a visual comparison alone.",
        },
    }
