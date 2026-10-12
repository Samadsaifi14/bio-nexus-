"""BBS-2 runnable: BLAST parser fidelity vs a frozen NCBI reference (MATRIX 16 extension).

The object under test is ``app.integrations.ncbi.parser.parse_blast_xml`` — the
normalizer that turns raw NCBI ``BlastOutput`` XML into the structured hit list
the API/pipeline serve.

Frozen references live next to this file:

* ``hbb_swissprot.xml``     — raw NCBI-format XML captured live from the
  EMBL-EBI ncbiblast REST endpoint (NCBI BlastOutput schema).
* ``reference.json``        — independently extracted reference values (literal
  text of the XML, first HSP per hit), pinned with the source shasum.

Each parsed field is compared against the reference under an explicit
tolerance rule (exact for identifiers/counts/alignment strings, small numeric
tolerance for float representations).  A download-parity pass then verifies
that every field survives JSON and CSV serialization losslessly, so any
download stream built from the normalized hits cannot silently alter values.

Exit codes:
  0 = full execution and all predeclared success criteria met
  1 = full execution but a comparison failed (visible, honest failure)
  2 = required external dependency unavailable -> requires_external record
"""

from __future__ import annotations

import argparse
import csv
import datetime as _dt
import hashlib
import io
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
RESULTS = HERE.parents[2] / "results" / "sequence" / "blast_parser"
BACKEND = REPO / "bioai-platform" / "backend"

REFERENCE_XML = HERE / "synthetic_structure.xml"  # overridden by reference.json["source_xml"]
REFERENCE_JSON = HERE / "reference.json"

TOP_N = 5

# Field-by-field comparison rules (documented in README.md).
STRING_EXACT = ("accession", "id", "description", "organism", "evalue_raw", "query_alignment", "hit_alignment", "midline")
INT_EXACT = ("length", "score", "identity", "positive", "gaps", "alignment_length", "query_from", "query_to", "hit_from", "hit_to", "query_length")
FLOAT_TOL = {
    "bit_score": 1e-3,
    "evalue": None,        # relative 1e-9 when ref != 0, else absolute 1e-300
    "identity_pct": 0.11,  # parser rounds to 1 dp; 0.11 covers any repr drift
}

# Canonical download column set (matches the BlastHitSummary shape the exports use).
DOWNLOAD_COLUMNS = [
    "accession", "id", "description", "organism", "evalue", "bit_score", "score",
    "identity_pct", "positive", "gaps", "alignment_length", "query_from", "query_to",
    "hit_from", "hit_to", "query_alignment", "hit_alignment", "midline", "evalue_raw",
]

FIELD_ORDER = STRING_EXACT + INT_EXACT + tuple(FLOAT_TOL)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _num_equal(actual: object, expected: object, rule) -> bool:
    if not isinstance(expected, (int, float)) or isinstance(expected, bool):
        return False
    actual_f, expected_f = float(actual), float(expected)
    if rule is None:
        if expected_f == 0.0:
            return abs(actual_f - expected_f) <= 1e-300
        return abs(actual_f - expected_f) / max(abs(expected_f), 1e-300) <= 1e-9
    return abs(actual_f - expected_f) <= rule


def compare_hit(idx: int, ref: dict, actual: dict) -> list[str]:
    failures = []
    for field in FIELD_ORDER:
        rv, av = ref.get(field), actual.get(field)
        if field in FLOAT_TOL:
            if not _num_equal(av, rv, FLOAT_TOL[field]):
                failures.append(
                    f"hit[{idx}].{field}: ref={rv!r} parsed={av!r}"
                )
        elif field in INT_EXACT:
            if int(av or 0) != int(rv or 0):
                failures.append(
                    f"hit[{idx}].{field}: ref={rv!r} parsed={av!r}"
                )
        elif field in STRING_EXACT:
            if str(av or "") != str(rv or ""):
                failures.append(
                    f"hit[{idx}].{field}: ref={rv[:60]!r} parsed={av[:60]!r} (maybe truncated)"
                )
    return failures


def download_parity(hits: list[dict]) -> dict:
    """JSON + CSV round-trips must preserve every parsed value verbatim."""
    level = 0
    details = []
    for i, hit in enumerate(hits[:TOP_N]):
        # JSON round trip.
        if json.loads(json.dumps(hit)) != hit:
            details.append(f"hit[{i}]: JSON round-trip altered values")
            continue
        # CSV round trip on the canonical column set.
        out = io.StringIO()
        writer = csv.DictWriter(out, fieldnames=DOWNLOAD_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerow(hit)
        rows = list(csv.DictReader(io.StringIO(out.getvalue())))
        if len(rows) != 1:
            details.append(f"hit[{i}]: CSV produced {len(rows)} rows")
            continue
        row = rows[0]
        ok = True
        for col in DOWNLOAD_COLUMNS:
            rv = hit.get(col)
            cell = row.get(col, "")
            if isinstance(rv, float):
                if abs(float(cell) - rv) > 1e-12:
                    ok = False
                    details.append(f"hit[{i}].{col}: csv={cell!r} parsed={rv!r}")
                    break
            elif isinstance(rv, int):
                if str(rv) != cell:
                    ok = False
                    details.append(f"hit[{i}].{col}: csv={cell!r} parsed={rv!r}")
                    break
            elif str(rv or "") != cell:
                ok = False
                details.append(f"hit[{i}].{col}: csv={cell!r} parsed={rv!r}")
                break
        if ok:
            level += 1
    return {"roundtrip_ok": len(details) == 0, "hits": level, "details": details}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--outdir", type=Path, default=RESULTS)
    parser.add_argument("--no-network", action="store_true", help="unused; this runner is offline by design")
    args = parser.parse_args()

    if not REFERENCE_XML.is_file() or not REFERENCE_JSON.is_file():
        record = {
            "benchmark": "bionexus-blast-parser-fidelity/v1",
            "status": "not_executed",
            "reason": "requires_external",
            "missing": ["frozen_reference_xml", "reference_json"],
            "recorded": _dt.date.today().isoformat(),
        }
        args.outdir.mkdir(parents=True, exist_ok=True)
        (args.outdir / "latest.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8", newline="")
        print("BLAST parser fidelity: not executed (frozen NCBI reference missing) -> requires_external record")
        return 2

    reference = json.loads(REFERENCE_JSON.read_text(encoding="utf-8"))
    xml_name = reference.get("source_xml", REFERENCE_XML.name)
    xml_path = REFERENCE_XML.parent / xml_name
    if not xml_path.is_file():
        xml_path = REFERENCE_XML
    xml_text = xml_path.read_text(encoding="utf-8")

    integrity_ok = sha256_bytes(xml_path.read_bytes()) == reference.get("source_xml_sha256")
    if not integrity_ok:
        args.outdir.mkdir(parents=True, exist_ok=True)
        (args.outdir / "latest.json").write_text(
            json.dumps({"benchmark": "bionexus-blast-parser-fidelity/v1", "status": "failed",
                        "reason": f"reference {xml_name} sha256 drifted from reference.json",
                        "status_rule": "integrity", "recorded": _dt.date.today().isoformat()}, indent=2) + "\n",
            encoding="utf-8", newline="")
        print(f"BLAST parser fidelity FAILED: {xml_name} sha256 differs from reference.json")
        return 1

    sys.path.insert(0, str(BACKEND))
    from app.integrations.ncbi.parser import parse_blast_xml

    parsed = parse_blast_xml(xml_text)
    if parsed.get("error"):
        record = {"benchmark": "bionexus-blast-parser-fidelity/v1", "status": "failed",
                  "reason": f"parser error: {parsed['error']}", "recorded": _dt.date.today().isoformat()}
        args.outdir.mkdir(parents=True, exist_ok=True)
        (args.outdir / "latest.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8", newline="")
        print(f"BLAST parser fidelity FAILED: parse error {parsed['error']}")
        return 1

    ref_hits = reference["hits"][:TOP_N]
    act_hits = parsed["hits"][:TOP_N]

    failures: list[str] = []
    if parsed["query_length"] != reference["query"]["length"]:
        failures.append(f"query_length: ref={reference['query']['length']} parsed={parsed['query_length']}")

    for i, (ref, act) in enumerate(zip(ref_hits, act_hits)):
        failures.extend(compare_hit(i, ref, act))

    counted = min(len(FIELD_ORDER) * len(ref_hits), 1)
    fields_ok = sum(1 for ref, act in zip(ref_hits, act_hits)
                    for f in FIELD_ORDER if _field_matches(f, ref.get(f), act.get(f)))
    fields_total = len(FIELD_ORDER) * len(ref_hits)
    fidelity_permille = round(fields_ok / fields_total * 1000) if fields_total else 1000

    parity = download_parity(parsed["hits"])

    passed = not failures and parity["roundtrip_ok"]
    record = {
        "benchmark": "bionexus-blast-parser-fidelity/v1",
        "status": "passed" if passed else "failed",
        "recorded": _dt.date.today().isoformat(),
        "origin": reference.get("origin", "unknown"),
        "source_xml": reference["source_xml"],
        "source_xml_sha256": reference["source_xml_sha256"],
        "capture_metadata": reference.get("capture_metadata", {}),
        "integrity_ok": integrity_ok,
        "program": reference["program"],
        "database": reference["database"],
        "top_n": TOP_N,
        "field_permille_exact_match": fidelity_permille,
        "fields_compared": fields_total,
        "tolerance_rules": {**{f: ("exact" if f in STRING_EXACT else "exact") for f in FIELD_ORDER},
                            **{f: ("rel 1e-9" if v is None else f"abs<={v}") for f, v in FLOAT_TOL.items()}},
        "download_parity": {"roundtrip_ok": parity["roundtrip_ok"], "hits_checked": parity["hits"],
                            "details": parity["details"][:10]},
        "failures": failures[:20],
    }
    args.outdir.mkdir(parents=True, exist_ok=True)
    (args.outdir / "latest.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8", newline="")
    if not passed:
        print(f"BLAST parser fidelity FAILED: {len(failures)} field failures, parity={parity['roundtrip_ok']}")
        for f in failures[:10]:
            print(f"  - {f}")
        return 1
    print(f"BLAST parser fidelity PASS: {fidelity_permille}/1000 field exactness "
          f"({fields_ok}/{fields_total}), download parity {parity['hits']}/{len(ref_hits)}")
    return 0


def _field_matches(field: str, rv, av) -> bool:
    if field in FLOAT_TOL:
        return _num_equal(av, rv, FLOAT_TOL[field])
    if field in INT_EXACT:
        return int(av or 0) == int(rv or 0)
    return str(av or "") == str(rv or "")


if __name__ == "__main__":
    raise SystemExit(main())
