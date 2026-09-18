"""Record/generate the BLAST parser reference bundle (offline + live modes).

Offline (default)
-----------------
Reads a frozen raw NCBI-schema BlastOutput XML (default: the synthetic
structural regression fixture) and independently extracts literal reference
values (first HSP per hit, raw text as reported) into ``reference.json`` with
a pinned source shasum.  The extraction deliberately re-reads the XML field
by field instead of reusing the parser under test, so the reference is an
independent witness of the XML content.

Live (--live)
-------------
Submits a real blastp query to NCBI's public BLAST (Blast.cgi CMD=Put), polls
CMD=Get until READY, saves the genuine NCBI ``BlastOutput`` XML (no namespace)
with ``origin: ncbi-live`` and capture metadata, then extracts the reference.
NCBI queue delays can be long; the runner makes one bounded attempt and exits
honestly if the search is not READY within ``--budget`` seconds.

Regenerating: run `python record_reference.py` after intentionally updating
the frozen XML (e.g. after a successful live capture against a newer
Swiss-Prot release).
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import re
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import httpx

HERE = Path(__file__).resolve().parent
DEFAULT_XML = HERE / "synthetic_structure.xml"
REFERENCE_JSON = HERE / "reference.json"

NCBI_BL = "https://blast.ncbi.nlm.nih.gov/Blast.cgi"

DEFAULT_QUERY = (
    "MVHLTPEEKSAVTALWGKVNVDEVGGEALGRLLVVYPWTQRFFESFGDLSTPDAVMGNPKVKAHGKKVLGAFSDGLAHLDNLKG"
    "TFATLSELHCDKLHVDPENFRLLGNVLVCVLAHHFGKEFTPPVQAAYQKVVAGVANALAHKYH"
)


def _text(el, tag):
    found = el.find(f".//{tag}")
    return found.text if found is not None and found.text else ""


def extract_reference(xml_text: str) -> tuple[dict, str]:
    """Return (hits, program_version) parsed independently from the XML."""
    root = ET.fromstring(xml_text)
    query_len = int(_text(root, "BlastOutput_query-len") or 0)
    version = _text(root, "BlastOutput_version")
    hits = []
    for hit in root.findall(".//Iteration//Hit"):
        acc = _text(hit, "Hit_accession")
        if not acc:
            continue
        length = int(_text(hit, "Hit_len") or 0)
        hsp = hit.find(".//Hsp")
        if hsp is None:
            continue
        desc = _text(hit, "Hit_def")
        organism = ""
        if "[" in desc and "]" in desc:
            organism = desc.split("[")[-1].rstrip("]")
            desc = desc.split("[")[0].strip()
        identity = int(_text(hsp, "Hsp_identity") or 0)
        align_len = int(_text(hsp, "Hsp_align-len") or 0)
        identity_pct = round(identity / align_len * 100, 1) if align_len else 0.0
        hits.append({
            "accession": acc,
            "id": _text(hit, "Hit_id"),
            "description": desc,
            "organism": organism,
            "length": length,
            "score": int(_text(hsp, "Hsp_score") or 0),
            "bit_score": float(_text(hsp, "Hsp_bit-score") or 0),
            "evalue_raw": _text(hsp, "Hsp_evalue") or "0",
            "evalue": float(_text(hsp, "Hsp_evalue") or 0),
            "identity": identity,
            "identity_pct": identity_pct,
            "positive": int(_text(hsp, "Hsp_positive") or 0),
            "gaps": int(_text(hsp, "Hsp_gaps") or 0),
            "alignment_length": int(_text(hsp, "Hsp_align-len") or 0),
            "query_from": int(_text(hsp, "Hsp_query-from") or 0),
            "query_to": int(_text(hsp, "Hsp_query-to") or 0),
            "hit_from": int(_text(hsp, "Hsp_hit-from") or 0),
            "hit_to": int(_text(hsp, "Hsp_hit-to") or 0),
            "query_alignment": _text(hsp, "Hsp_qseq"),
            "hit_alignment": _text(hsp, "Hsp_hseq"),
            "midline": _text(hsp, "Hsp_midline"),
        })
    return hits, version


def capture_ncbi_live(xml_path: Path, query: str, budget: int) -> dict:
    """Submit blastp to NCBI, poll, save the genuine XML when READY."""
    with httpx.Client(timeout=30, follow_redirects=True) as client:
        r = client.post(NCBI_BL, data={
            "CMD": "Put", "PROGRAM": "blastp", "DATABASE": "swissprot",
            "QUERY": query, "HITLIST_SIZE": 5, "EXPECT": 10.0,
            "MATRIX_NAME": "BLOSUM62", "GAPCOSTS": "11 1",
            "EMAIL": "bioflow@example.com",
        })
        r.raise_for_status()
        m = re.search(r"RID\s*=\s*(\S+)", r.text)
        if not m:
            raise RuntimeError("NCBI did not return a RID")
        rid = m.group(1).strip()
        rtoe = (re.search(r"RTOE\s*=\s*(\S+)", r.text) or [None, None])[1]

        deadline = time.time() + budget
        while time.time() < deadline:
            info = client.get(NCBI_BL, params={"CMD": "Get", "RID": rid, "FORMAT_OBJECT": "SearchInfo"}).text
            if "Status=READY" in info:
                break
            time.sleep(5)
        else:
            raise RuntimeError(f"NCBI search {rid} not READY within {budget}s (queue)")

        body = client.get(NCBI_BL, params={
            "CMD": "Get", "RID": rid, "FORMAT_TYPE": "XML",
            "ALIGNMENTS": 5, "DESCRIPTIONS": 5,
        }).text
        if "<BlastOutput" not in body:
            raise RuntimeError(f"NCBI {rid} returned a non-XML body")
        xml_path.write_text(body, encoding="utf-8")
        return {"rid": rid, "rtoe_h": str(rtoe), "captured_at": _dt.datetime.utcnow().isoformat() + "Z"}


def write_reference(xml_path: Path, origin: str, program: str, database: str,
                    capture_metadata: dict | None = None) -> dict:
    xml_text = xml_path.read_text(encoding="utf-8")
    if "<BlastOutput" not in xml_text:
        raise RuntimeError(f"{xml_path.name} is not NCBI-schema BlastOutput XML")
    hits, version = extract_reference(xml_text)
    query_len = _query_length_from_xml(xml_text) or (hits[0]["query_to"] if hits else 0)
    ref = {
        "schema": "bionexus-blast-parser-reference/v1",
        "origin": origin,
        "capture_metadata": capture_metadata or {},
        "program": program,
        "database": database,
        "blast_output_version": version,
        "query": {"length": query_len},
        "source_xml": xml_path.name,
        "source_xml_sha256": hashlib.sha256(xml_path.read_bytes()).hexdigest(),
        "hits": hits,
    }
    return ref


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--xml", type=Path, default=DEFAULT_XML, help="BlastOutput XML to read")
    ap.add_argument("--origin", default="synthetic-structural",
                    help="origin label recorded in reference.json")
    ap.add_argument("--program", default="blastp")
    ap.add_argument("--database", default="swissprot (frozen at capture)")
    ap.add_argument("--live", action="store_true", help="capture a genuine NCBI reference first")
    ap.add_argument("--query", default=DEFAULT_QUERY)
    ap.add_argument("--budget", type=int, default=240, help="live NCBI poll budget (s)")
    args = ap.parse_args()

    xml_path = args.xml
    if args.live:
        xml_path = HERE / f"ncbi_live_{_dt.datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}.xml"
        try:
            capture_meta = capture_ncbi_live(xml_path, args.query, args.budget)
            print(f"live capture saved: {xml_path.name}")
        except RuntimeError as exc:
            print(f"LIVE CAPTURE NOT AVAILABLE: {exc}")
            print("reference.json left untouched; run offline mode with an existing frozen XML")
            return 2
        ref = write_reference(xml_path, origin="ncbi-live", program=args.program,
                              database=args.database, capture_metadata=capture_meta)
    else:
        ref = write_reference(xml_path, origin=args.origin, program=args.program,
                              database=args.database)

    REFERENCE_JSON.write_text(json.dumps(ref, indent=2) + "\n", encoding="utf-8", newline="")
    print(f"reference.json: origin={ref['origin']} source_xml={ref['source_xml']} "
          f"hits={len(ref['hits'])} query_length={ref['query']['length']} "
          f"version={ref.get('blast_output_version', 'unknown')}")
    return 0


def _query_length_from_xml(xml_text: str) -> int:
    m = re.search(r"<BlastOutput_query-len>(\d+)</BlastOutput_query-len>", xml_text)
    return int(m.group(1)) if m else 0


if __name__ == "__main__":
    sys.exit(main())