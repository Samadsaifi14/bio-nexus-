"""Accession-recovery control over an actually downloaded complete reference.

Inputs are canonical sequences extracted from that same frozen reference.
This measures engine/routing/accession recovery, not novel-protein accuracy.
"""
from __future__ import annotations
import argparse
import asyncio
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys


async def run(root, output, panel_path):
    from app.tools.blast import BlastTool
    from app.tools.blast_local import _reference
    panel = json.loads(panel_path.read_text())
    criteria = panel["predeclared_success_criteria"]
    manifest = _reference(str(root.resolve()), (root / "manifest.json").stat().st_mtime_ns)
    if "complete UniProtKB/Swiss-Prot" not in manifest["scope"]:
        raise RuntimeError("Full-reference benchmark requires a complete official snapshot")
    output.mkdir(parents=True, exist_ok=True)
    outcomes = []
    for control in panel["queries"]:
        accession = control["expected_accessions"][0]
        sequence = "".join(subprocess.run(["blastdbcmd", "-db", str(root / "swissprot"),
            "-entry", accession, "-outfmt", "%s"], capture_output=True, text=True,
            check=True, timeout=30).stdout.split())
        if len(sequence) < 20:
            raise RuntimeError("Reference control sequence is missing")
        (output / f"{control['id']}.fasta").write_text(f">{accession}\n{sequence}\n")
        result = await BlastTool().run_uncached({"sequence": sequence, "program": "blastp",
            "database": "uniprotkb_swissprot", "max_hits": panel["program_settings"]["max_hits_requested"]})
        if result.get("source") != "local-blast+" or result.get("search_complete") is not True:
            raise RuntimeError("Production path did not execute the declared local reference")
        (output / f"{control['id']}.xml").write_text(result["raw_result_xml"])
        hits = result["hits"][:criteria["max_recovery_rank"]]
        rank = next((i+1 for i, hit in enumerate(hits)
                     if hit["accession"] in control["expected_accessions"]), None)
        outcomes.append({"id": control["id"], "expected_accessions": control["expected_accessions"],
            "essential": control["essential"], "query_length": len(sequence),
            "query_sha256": hashlib.sha256(sequence.encode()).hexdigest(),
            "recovered_rank": rank, "recovered": rank is not None,
            "top_hits": [{"accession": h["accession"], "identity_pct": h["identity_pct"],
                          "bit_score": h["bit_score"], "evalue": h["evalue"]} for h in hits]})
    fraction = sum(row["recovered"] for row in outcomes) / len(outcomes)
    essential = all(row["recovered"] for row in outcomes if row["essential"])
    passed = (len(outcomes) >= criteria["min_queries"] and
              fraction >= criteria["recovery_threshold_frac"] and
              (essential or not criteria["essential_required"]))
    report = {"benchmark": "local-swissprot-production-accession-recovery/v1",
        "status": "passed" if passed else "failed", "executed": True,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "reference": manifest, "n_queries": len(outcomes), "n_recovered": sum(o["recovered"] for o in outcomes),
        "essential_recovered": essential, "criteria": criteria, "queries": outcomes,
        "limitations": ["Canonical queries originate in the searched snapshot: accession-recovery positive controls only.",
                        "No claim of novel sequence function, homology-transfer accuracy, or external NCBI service availability."]}
    (output / "latest.json").write_text(json.dumps(report, indent=2) + "\n")
    print("LOCAL_BLAST_BENCHMARK=" + json.dumps(report, sort_keys=True))
    return 0 if passed else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("reference", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("panel", type=Path)
    args = parser.parse_args()
    sys.exit(asyncio.run(run(args.reference, args.output, args.panel)))
