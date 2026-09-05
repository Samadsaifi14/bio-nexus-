"""Milestone 2 — Benchmark Repository (BBS-1 expansion).

A curated catalog of benchmarks (protein DNA / docking / primers / UniProt /
PDB / MSA / phylogeny / NGS), each with expected outputs, accepted tolerance,
ground truth and a citation. A deterministic runner executes a recorded
experiment against a benchmark, compares measured vs expected within tolerance,
and stores a benchmark_runs row.

The catalog is seeded from JSON files under app/data/benchmarks/ so extending
the repository is data-entry, not code. All writes are best-effort.
"""

from __future__ import annotations

import json
import logging
import math
import os
import time
from datetime import datetime, timezone

from app.services.supabase import get_supabase

logger = logging.getLogger(__name__)

BENCHMARKS_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "benchmarks")

# Numeric tolerance default (absolute) when a metric has no explicit tolerance.
DEFAULT_TOLERANCE = 0.5


# --- Catalog registry -----------------------------------------------------

def list_benchmarks(category: str | None = None) -> list[dict]:
    try:
        q = get_supabase().table("benchmarks").select("*").order("category")
        if category:
            q = q.eq("category", category)
        resp = q.execute()
        return resp.data or []
    except Exception as e:
        logger.warning("Benchmark list failed: %s", e)
        return []


def get_benchmark(benchmark_id: str) -> dict | None:
    try:
        resp = get_supabase().table("benchmarks").select("*").eq("id", benchmark_id).limit(1).execute()
        return resp.data[0] if resp.data else None
    except Exception as e:
        logger.warning("Benchmark get failed: %s", e)
        return None


def load_benchmark_files() -> list[dict]:
    """Read all benchmark catalog JSON files from app/data/benchmarks/."""
    records: list[dict] = []
    if not os.path.isdir(BENCHMARKS_DIR):
        return records
    for fname in sorted(os.listdir(BENCHMARKS_DIR)):
        if not fname.endswith(".json"):
            continue
        path = os.path.join(BENCHMARKS_DIR, fname)
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                records.extend(data)
            elif isinstance(data, dict) and data.get("benchmarks"):
                records.extend(data["benchmarks"])
        except Exception as e:
            logger.warning("Skipping benchmark file %s: %s", fname, e)
    return records


def _benchmark_row(record: dict, omit_section: bool = False, omit_depth: bool = False) -> dict:
    """Map one catalog record to its benchmarks table row (Component 6).

    Pure and unit-testable: pulls the fields that survive into the database,
    including difficulty and registry_version with registry defaults.
    """
    row = {
        "category": record["category"],
        "name": record["name"],
        "description": record.get("description", ""),
        "input": record.get("input", {}),
        "expected_output": record.get("expected_output", {}),
        "tolerance": record.get("tolerance", {}),
        "ground_truth": record.get("ground_truth", ""),
        "citation": record.get("citation", ""),
        "source": record.get("source", "bbs-1"),
        "stage": record.get("stage", "curated"),
    }
    if not omit_depth:
        row["difficulty"] = record.get("difficulty", "easy")
        row["registry_version"] = record.get("version", 1)
    if not omit_section:
        row["section"] = record.get("section", "blast")
    return row


def seed_benchmarks() -> int:
    """Upsert the JSON catalog into the database by (category, name).
    Returns the number of records upserted (best-effort).

    Tolerates missing columns exactly like migration 009's `section`: if the
    first insert fails on `section`, seeding retries without it; if it fails
    on the Component 6 depth columns (difficulty/registry_version, migration
    010), seeding retries without those too. Later records reuse the disabled
    flags so the whole catalog still seeds on partially-migrated databases.
    """
    records = load_benchmark_files()
    if not records:
        return 0
    count = 0
    omit_section = False
    omit_depth = False
    try:
        for rec in records:
            row = _benchmark_row(rec, omit_section, omit_depth)
            try:
                get_supabase().table("benchmarks") \
                    .upsert(row, on_conflict="category,name") \
                    .execute()
                count += 1
            except Exception as e:
                msg = str(e)
                if not omit_section and "section" in msg:
                    omit_section = True
                    logger.warning("benchmarks.section column missing - retrying without it")
                elif not omit_depth and any(c in msg for c in ("difficulty", "registry_version")):
                    omit_depth = True
                    logger.warning("benchmarks depth columns missing - retrying without them")
                else:
                    logger.warning("Benchmark seed failed for %s: %s", rec.get("name"), e)
                    continue
                get_supabase().table("benchmarks") \
                    .upsert(_benchmark_row(rec, omit_section, omit_depth),
                            on_conflict="category,name") \
                    .execute()
                count += 1
    except Exception as e:
        logger.warning("Benchmark seed failed after %d records: %s", count, e)
    logger.info("Benchmark catalog seeded: %d records", count)
    return count


# --- Benchmark runner -----------------------------------------------------

#: Sections a full pipeline result context always contains. When context_json
#: carries these it IS the result context (wizard path); otherwise it is only
#: the input parameters and the real result lives in the storage artifact.
_RESULT_SECTIONS = ("blast", "uniprot", "msa", "phylo", "domains", "pathway_enrichment", "alphafold", "interpret")


def _fetch_job_context(job_id: str) -> dict | None:
    """Read the stored pipeline context for a job (context_json or storage)."""
    try:
        resp = get_supabase().table("jobs").select("context_json,storage_url").eq("id", job_id).limit(1).execute()
        if not resp.data:
            return None
        row = resp.data[0]
        inline = row.get("context_json")
        if isinstance(inline, dict) and any(k in inline for k in _RESULT_SECTIONS):
            return inline
        if row.get("storage_url"):
            from app.services.artifact_storage import download_json
            return download_json(row["storage_url"])
        return inline if isinstance(inline, dict) else None
    except Exception as e:
        logger.warning("Benchmark context fetch failed (job %s): %s", job_id, e)
    return None


def _metric_value(context: dict, section: str, key: str):
    """Pull a metric value from a job's stored context."""
    try:
        seg = context.get(section) or {}
        if key == "top_hit_accession":
            return (seg.get("top_hit") or {}).get("accession")
        if key == "top_hit_identity":
            return (seg.get("top_hit") or {}).get("identity_pct")
        if key == "top_hit_description":
            return (seg.get("top_hit") or {}).get("description")
        if key == "hit_count":
            return seg.get("count")
        if key == "domain_count":
            domains = seg.get("domains")
            return len(domains) if isinstance(domains, list) else None
        if key == "has_alignment":
            return bool(seg.get("aln_fasta"))
        if key == "has_newick":
            return bool(seg.get("phylotree_newick"))
        if key == "gene_name":
            names = seg.get("gene_names") or []
            return names[0] if names else None
        return seg.get(key)
    except Exception:
        return None


def compare_metric(actual, expected, tolerance: float) -> bool:
    """Compare one metric.

    - Dict matcher `{"contains": "..."}` passes when the actual string
      contains the substring (used for species-agnostic top-hit checks).
    - Dict matcher `{"min": x}` passes when actual >= x (quantitative floors).
    - Dict matcher `{"max": x}` passes when actual <= x (quantitative ceilings).
    - Numbers match within absolute tolerance.
    - Otherwise exact string match.
    Missing/None actual is never a pass (no silent success).
    """
    if actual is None:
        return False
    if isinstance(expected, dict) and isinstance(expected.get("contains"), str):
        return isinstance(actual, str) and expected["contains"] in actual
    if isinstance(expected, dict) and "min" in expected and isinstance(actual, (int, float)):
        try:
            return float(actual) >= float(expected["min"])
        except (TypeError, ValueError):
            return False
    if isinstance(expected, dict) and "max" in expected and isinstance(actual, (int, float)):
        try:
            return float(actual) <= float(expected["max"])
        except (TypeError, ValueError):
            return False
    if isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
        try:
            return abs(float(actual) - float(expected)) <= float(tolerance)
        except (TypeError, ValueError):
            return False
    return str(actual) == str(expected)


def run_benchmark(benchmark_id: str, job_id: str) -> dict:
    """Execute a benchmark against a recorded experiment.

    Compares the job's stored context against expected_output within tolerance
    and writes a benchmark_runs row. Returns the run summary (identical to what
    is persisted, so callers can verify even if the DB write fails).
    """
    bench = get_benchmark(benchmark_id)
    t0 = time.time()
    if not bench:
        summary = {"status": "error", "error": "benchmark not found"}
        return summary

    context = _fetch_job_context(job_id)
    summary = {
        "benchmark_id": benchmark_id,
        "job_id": job_id,
        "category": bench.get("category"),
        "name": bench.get("name"),
        "status": "failed",
        "metrics": {},
        "passed_checks": {},
    }
    if not context:
        summary["status"] = "error"
        summary["error"] = "job context not found"
        return summary

    section = bench.get("section", "blast")
    expected = bench.get("expected_output") or {}
    tolerances = bench.get("tolerance") or {}
    all_pass = True
    for key, exp_val in expected.items():
        actual = _metric_value(context, section, key)
        tol = tolerances.get(key, DEFAULT_TOLERANCE)
        passed = compare_metric(actual, exp_val, tol)
        summary["metrics"][key] = {
            "actual": actual,
            "expected": exp_val,
            "tolerance": tol,
        }
        summary["passed_checks"][key] = passed
        if not passed:
            all_pass = False

    summary["status"] = "passed" if all_pass else "failed"
    summary["runtime_s"] = round(time.time() - t0, 3)

    try:
        get_supabase().table("benchmark_runs").insert({
            "benchmark_id": benchmark_id,
            "status": summary["status"],
            "metrics": summary["metrics"],
            "passed_checks": summary["passed_checks"],
            "runtime_s": summary["runtime_s"],
        }).execute()
    except Exception as e:
        logger.warning("Benchmark run store failed: %s", e)
    return summary


# --- Statistical summary --------------------------------------------------

def batch_summary(category: str | None = None) -> dict:
    """Per-category pass/fail statistics across all recorded benchmark runs."""
    out = {"total_runs": 0, "passed": 0, "failed": 0, "by_category": {}}
    try:
        resp = get_supabase().table("benchmark_runs").select("status,passed_checks").execute()
        runs = resp.data or []
    except Exception as e:
        logger.warning("Benchmark run query failed: %s", e)
        return out
    for r in runs:
        out["total_runs"] += 1
        out["passed" if r.get("status") == "passed" else "failed"] += 1
    return out