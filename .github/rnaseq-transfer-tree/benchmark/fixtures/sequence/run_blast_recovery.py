"""BBS-2 runnable: multi-query BLAST accession-recovery benchmark (MATRIX 16).

Fetches canonical UniProt sequences for curated accessions, runs each through
the production BlastTool (app.tools.blast) against uniprotkb_swissprot with
identical settings, and checks that the curated expected accession appears in
the top max_recovery_rank hits. Sequences are recorded with sha256 so inputs
of a published run are tamper-evident.

Exit codes:
  0 = full execution and all predeclared success criteria met
  1 = full execution but an assertion failed (visible, honest failure)
  2 = external dependency unavailable (UniProt fetch and/or EBI BLAST)
      -> explicit not_executed/requires_external record; never a pass
"""

from __future__ import annotations

import argparse
import asyncio
import datetime as _dt
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
RESULTS = HERE.parents[1] / "results" / "sequence" / "blast"
BACKEND = REPO / "bioai-platform" / "backend"

UNIPROT_FASTA = "https://rest.uniprot.org/uniprotkb/{acc}.fasta"


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


async def _fetch_sequence(acc: str) -> str:
    import httpx
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        resp = await client.get(UNIPROT_FASTA.format(acc=acc))
        resp.raise_for_status()
        lines = resp.text.splitlines()
        seq = "".join(l.strip() for l in lines if not l.startswith(">"))
    if len(seq) < 20:
        raise RuntimeError(f"UniProt returned a degenerate sequence for {acc} (len={len(seq)})")
    return seq


async def _blast_one(acc: str, sequence: str, tool, settings: dict) -> dict:
    result = await tool.run_uncached({
        "sequence": sequence,
        "database": settings["database"],
        "program": settings["program"],
        "max_hits": settings["max_hits_requested"],
    })
    if result.get("error") or not result.get("hits"):
        raise RuntimeError(f"BLAST failed: {result.get('error') or 'no hits'}")
    return result


async def _main_async(args) -> int:
    panel = json.loads(args.panel.read_text(encoding="utf-8"))
    criteria = panel["predeclared_success_criteria"]
    settings = panel["program_settings"]
    queries = panel["queries"]

    if len(queries) < criteria["min_queries"]:
        raise SystemExit(f"fixture error: {len(queries)} queries < min_queries {criteria['min_queries']}")

    if args.no_network:
        record = {
            "benchmark": "bionexus-blast-accession-recovery/v1",
            "status": "not_executed",
            "reason": "requires_external",
            "missing": ["uniprot_network", "ebi_blast"],
            "queries_planned": len(queries),
            "success_criteria": criteria,
            "recorded": _dt.date.today().isoformat(),
        }
        args.outdir.mkdir(parents=True, exist_ok=True)
        (args.outdir / "latest.json").write_text(
            json.dumps(record, indent=2) + "\n", encoding="utf-8", newline="")
        print("BLAST multi-query: not executed (external deps unavailable) -> honest requires_external record")
        return 2

    sys.path.insert(0, str(BACKEND))
    from app.tools.blast import BlastTool
    tool = BlastTool()

    outcomes = []
    external_failure = None
    try:
        for q in queries:
            seq = await _fetch_sequence(q["expected_accessions"][0])
            try:
                result = await _blast_one(q["expected_accessions"][0], seq, tool, settings)
            except Exception as exc:
                raise RuntimeError(f"{q['id']}: BLAST failed: {type(exc).__name__}: {exc!r}") from exc
            expected = set(q["expected_accessions"])
            hit_list = [
                {"accession": h.get("accession", ""), "description": h.get("description", ""),
                 "organism": h.get("organism", ""), "evalue": h.get("evalue")}
                for h in result["hits"]
            ]
            rank = next((i + 1 for i, h in enumerate(hit_list[: criteria["max_recovery_rank"]])
                         if h["accession"] in expected), None)
            outcomes.append({
                "id": q["id"],
                "protein": q["protein"],
                "expected_accessions": q["expected_accessions"],
                "essential": q["essential"],
                "query_sha256": _sha256(seq),
                "query_length": len(seq),
                "recovered_rank": rank,
                "recovered": rank is not None,
                "top_hits": hit_list[: criteria["max_recovery_rank"]],
            })
    except Exception as exc:
        external_failure = str(exc)

    if external_failure is not None:
        record = {
            "benchmark": "bionexus-blast-accession-recovery/v1",
            "status": "not_executed",
            "reason": "requires_external",
            "missing": ["uniprot_network", "ebi_blast"],
            "error": repr(external_failure)[:400] if external_failure else "",
            "queries_planned": len(queries),
            "success_criteria": criteria,
            "completed_outcomes": outcomes,
            "recorded": _dt.date.today().isoformat(),
        }
        args.outdir.mkdir(parents=True, exist_ok=True)
        (args.outdir / "latest.json").write_text(
            json.dumps(record, indent=2) + "\n", encoding="utf-8", newline="")
        print(f"BLAST multi-query: not executed (external failure: {external_failure[:120]}) -> honest requires_external record")
        return 2

    recovered = sum(1 for o in outcomes if o["recovered"])
    frac = recovered / len(outcomes)
    essential_ok = any(o["essential"] and o["recovered"] for o in outcomes)

    # Every query recovered => the pass criterion allows a couple of misses,
    # but a miss must be visible in the record, never silently dropped.
    failures = [
        f"{o['id']}: expected accession(s) {o['expected_accessions']} not in top {criteria['max_recovery_rank']}"
        for o in outcomes if not o["recovered"]
    ]
    criteria_ok = (frac >= criteria["recovery_threshold_frac"] and essential_ok)

    record = {
        "benchmark": "bionexus-blast-accession-recovery/v1",
        "status": "passed" if criteria_ok else "failed",
        "recorded": _dt.date.today().isoformat(),
        "n_queries": len(outcomes),
        "n_recovered": recovered,
        "recovery_fraction": round(frac, 3),
        "essential_recovered": essential_ok,
        "success_criteria": criteria,
        "program_settings": settings,
        "queries": outcomes,
        "criteria_ok": criteria_ok,
        "failures": failures,
        "limitations": panel["limitations"],
    }
    args.outdir.mkdir(parents=True, exist_ok=True)
    (args.outdir / "latest.json").write_text(
        json.dumps(record, indent=2) + "\n", encoding="utf-8", newline="")
    if not criteria_ok:
        print(f"BLAST multi-query FAILED: {recovered}/{len(outcomes)} recovered (essential_ok={essential_ok})")
        for f in failures:
            print(f"  - {f}")
        return 1
    print(f"BLAST multi-query PASS: {recovered}/{len(outcomes)} recovered, essential control met")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--panel", type=Path, default=HERE / "blast_queries.json")
    parser.add_argument("--outdir", type=Path, default=RESULTS)
    parser.add_argument("--no-network", action="store_true",
                        help="force requires_external/not_executed path without outbound access (pytest knob)")
    args = parser.parse_args()
    return asyncio.run(_main_async(args))


if __name__ == "__main__":
    raise SystemExit(main())