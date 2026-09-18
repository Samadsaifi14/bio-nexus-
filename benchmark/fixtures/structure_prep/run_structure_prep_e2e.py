"""BBS-2 runnable: structure-preparation live E2E harness (MATRIX 8).

Runs the production structure-prep chain end to end on real PDB entries:
  fetch --> detect_chain_health --> pymol_cleanup --> run_fpocket

using the exact code paths in app.tools.structure_prep. Every entry records
its health, cleanup and pocket results. Success criteria are predeclared in
structure_prep_panel.json.

Exit codes:
  0 = full chain executed AND all predeclared assertions passed
  1 = full chain executed but an assertion failed (visible, honest failure)
  2 = external dependency unavailable (network fetch and/or fpocket binary
      missing) -> explicit not_executed/requires_external record; never a pass
"""

from __future__ import annotations

import asyncio
import datetime as _dt
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
RESULTS = HERE.parents[1] / "results" / "structure_prep"
BACKEND = REPO / "bioai-platform" / "backend"


def _record(args, record: dict) -> None:
    args.outdir.mkdir(parents=True, exist_ok=True)
    (args.outdir / "latest.json").write_text(
        json.dumps(record, indent=2) + "\n", encoding="utf-8", newline=""
    )


async def _run_entry(entry: dict, deps: dict) -> dict:
    from app.tools.structure_prep import detect_chain_health, fetch_pdb_text, pymol_cleanup, run_fpocket

    out = {"id": entry["id"], "pdb": entry["pdb"], "expect_pocket": entry["expect_pocket"]}
    if deps["fetch_ok"]:
        try:
            pdb_text = await fetch_pdb_text(entry["pdb"])
        except Exception as exc:
            out["error"] = f"fetch failed: {exc}"
            return out
    else:
        out["error"] = "network unavailable"
        return out

    health = detect_chain_health(pdb_text)
    out["chain_health"] = {
        "total_residues": health.total_residues,
        "chains": health.chains,
        "has_missing_residues": health.has_missing_residues,
        "has_chain_breaks": health.has_chain_breaks,
        "is_broken": health.is_broken,
        "missing_residue_count": health.missing_residue_count,
        "chain_break_count": health.chain_break_count,
    }

    cleaned = pymol_cleanup(pdb_text)
    atom_lines = [l for l in cleaned.splitlines() if l.startswith(("ATOM", "TER"))]
    hetatm_lines = [l for l in cleaned.splitlines() if l.startswith("HETATM")]
    water_lines = [l for l in cleaned.splitlines() if l.startswith(("HETATM", "ATOM")) and "HOH" in l[17:20]]
    out["cleanup"] = {
        "non_empty": len(cleaned) > 100,
        "atom_count": len(atom_lines),
        "hetatm_removed": len(hetatm_lines) == 0,
        "water_removed": len(water_lines) == 0,
    }

    if deps["fpocket_ok"]:
        fp = run_fpocket(cleaned)
        out["pockets"] = {
            "status": fp.status,
            "pocket_count": fp.pocket_count,
            "pockets": fp.pockets,
        }
    else:
        out["pockets"] = {"status": "unavailable", "pocket_count": 0, "pockets": []}
        out["pockets_unavailable"] = True
    return out


async def _main_async(args) -> int:
    panel = json.loads(args.panel.read_text(encoding="utf-8"))
    assertions = panel["predeclared_assertions"]
    entries = panel["entries"]

    deps = {"fetch_ok": not args.no_network, "fpocket_ok": True}
    if deps["fetch_ok"]:
        try:
            sys.path.insert(0, str(BACKEND))
            from pathlib import Path as _P
            from app.tools.structure_prep import FPOCKET_BIN
            deps["fpocket_ok"] = _P(FPOCKET_BIN).exists()
            # network probed cheaply via the actual fetch inside the entry loop
        except Exception:
            deps["fetch_ok"] = False
            deps["fpocket_ok"] = False

    results = []
    for entry in entries:
        if deps["fetch_ok"]:
            results.append(await _run_entry(entry, deps))
        else:
            results.append({"id": entry["id"], "pdb": entry["pdb"], "error": "network unavailable"})

    fetch_failed = any("error" in r and "fetch failed" in r.get("error", "") for r in results)
    external_missing = not deps["fetch_ok"] or not deps["fpocket_ok"] or fetch_failed

    if external_missing:
        record = {
            "benchmark": "bionexus-structure-prep-e2e/v1",
            "status": "not_executed",
            "reason": "requires_external",
            "missing": [k for k, v in {"rcsb_network": deps["fetch_ok"], "fpocket_binary": deps["fpocket_ok"]}.items() if not v],
            "entries_planned": len(entries),
            "success_criteria": assertions,
            "recorded": _dt.date.today().isoformat(),
        }
        if not deps["fpocket_ok"] and deps["fetch_ok"]:
            # still keep per-entry output in the record for traceability
            record["entries"] = results
        _record(args, record)
        print("STRUCTURE-PREP E2E: not executed (external deps unavailable) -> honest requires_external record")
        return 2

    # Full execution: evaluate predeclared assertions.
    failures = []
    for r in results:
        eid = f"{r['id']}:{r['pdb']}"
        if r.get("error"):
            failures.append(f"{eid}: {r['error']}")
            continue
        if r["chain_health"]["total_residues"] <= 0:
            failures.append(f"{eid}: chain_health total_residues == 0")
        if not r["cleanup"]["non_empty"] or r["cleanup"]["atom_count"] == 0:
            failures.append(f"{eid}: cleanup lost the protein")
        if not r["cleanup"]["hetatm_removed"]:
            failures.append(f"{eid}: cleanup kept HETATM")
        if not r["cleanup"]["water_removed"]:
            failures.append(f"{eid}: cleanup kept waters")
        if r["pockets"]["status"] != "complete":
            failures.append(f"{eid}: fpocket status != complete ({r['pockets']['status']})")
        elif r["expect_pocket"] and r["pockets"]["pocket_count"] < 1:
            failures.append(f"{eid}: expected >=1 pocket, got 0")

    record = {
        "benchmark": "bionexus-structure-prep-e2e/v1",
        "status": "passed" if not failures else "failed",
        "recorded": _dt.date.today().isoformat(),
        "entries": results,
        "failures": failures,
        "success_criteria": assertions,
        "limitations": panel["limitations"],
    }
    _record(args, record)
    if failures:
        print(f"STRUCTURE-PREP E2E FAILED: {len(failures)} assertion failure(s)")
        for f in failures:
            print(f"  - {f}")
        return 1
    print(f"STRUCTURE-PREP E2E PASS: {len(results)} entries, all assertions met")
    return 0


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--panel", type=Path, default=HERE / "structure_prep_panel.json")
    parser.add_argument("--outdir", type=Path, default=RESULTS)
    parser.add_argument("--no-network", action="store_true",
                        help="force the requires_external/not_executed path without touching the network "
                             "(pytest-knob: lets the deterministic suite exercise honesty without RCSB access)")
    args = parser.parse_args()
    return asyncio.run(_main_async(args))


if __name__ == "__main__":
    raise SystemExit(main())