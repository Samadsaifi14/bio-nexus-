"""
Parse NCBI BLAST XML output into structured hit list.

Raw XML is always stored to R2 first; parsing happens from
the stored copy, never inline with the API request.
"""

import xml.etree.ElementTree as ET
from typing import List, Optional


def parse_blast_xml(raw_xml: str) -> dict:
    try:
        root = ET.fromstring(raw_xml)
    except ET.ParseError as e:
        return {"error": f"XML parse error: {e}", "hits": []}

    ns = {"": "http://www.ncbi.nlm.nih.gov"}
    query_len_el = root.find(".//BlastOutput_query-len")
    query_len = int(query_len_el.text) if query_len_el is not None else 0

    hits = []
    for iteration in root.findall(".//Iteration"):
        for hit_el in iteration.findall(".//Hit"):
            hit = _parse_hit(hit_el)
            if hit is not None:
                hits.append(hit)

    return {
        "query_length": query_len,
        "hits": hits,
        "count": len(hits),
    }


def _parse_hit(hit_el: ET.Element) -> Optional[dict]:
    acc = _text(hit_el, "Hit_accession")
    if not acc:
        return None
    hit_id = _text(hit_el, "Hit_id")
    def_line = _text(hit_el, "Hit_def")
    accession = acc
    description = def_line or ""
    if " " in def_line:
        parts = def_line.split(" ", 1)
        if parts[0] == acc or parts[0] == hit_id:
            description = parts[1] if len(parts) > 1 else ""

    organism = ""
    if "[" in description and "]" in description:
        organism = description.split("[")[-1].rstrip("]")
        description = description.split("[")[0].strip()

    hsps = hit_el.findall(".//Hsp")
    top_hsp = _parse_hsp(hsps[0]) if hsps else None

    return {
        "accession": accession,
        "id": hit_id,
        "description": description,
        "organism": organism,
        "length": int(_text(hit_el, "Hit_len") or 0),
        "score": top_hsp.get("score", 0) if top_hsp else 0,
        "bit_score": top_hsp.get("bit_score", 0) if top_hsp else 0,
        "evalue": top_hsp.get("evalue", 0) if top_hsp else 0,
        "identity": top_hsp.get("identity", 0) if top_hsp else 0,
        "identity_pct": top_hsp.get("identity_pct", 0) if top_hsp else 0,
        "positive": top_hsp.get("positive", 0) if top_hsp else 0,
        "gaps": top_hsp.get("gaps", 0) if top_hsp else 0,
        "alignment_length": top_hsp.get("alignment_length", 0) if top_hsp else 0,
        "query_from": top_hsp.get("query_from", 0) if top_hsp else 0,
        "query_to": top_hsp.get("query_to", 0) if top_hsp else 0,
        "hit_from": top_hsp.get("hit_from", 0) if top_hsp else 0,
        "hit_to": top_hsp.get("hit_to", 0) if top_hsp else 0,
        "query_alignment": top_hsp.get("query_alignment", "") if top_hsp else "",
        "hit_alignment": top_hsp.get("hit_alignment", "") if top_hsp else "",
        "midline": top_hsp.get("midline", "") if top_hsp else "",
    }


def _parse_hsp(hsp_el: ET.Element) -> dict:
    score = int(_text(hsp_el, "Hsp_score") or 0)
    bit_score = float(_text(hsp_el, "Hsp_bit-score") or 0)
    evalue = float(_text(hsp_el, "Hsp_evalue") or 0)
    identity = int(_text(hsp_el, "Hsp_identity") or 0)
    positive = int(_text(hsp_el, "Hsp_positive") or 0)
    gaps = int(_text(hsp_el, "Hsp_gaps") or 0)
    align_len = int(_text(hsp_el, "Hsp_align-len") or 0)
    query_from = int(_text(hsp_el, "Hsp_query-from") or 0)
    query_to = int(_text(hsp_el, "Hsp_query-to") or 0)
    hit_from = int(_text(hsp_el, "Hsp_hit-from") or 0)
    hit_to = int(_text(hsp_el, "Hsp_hit-to") or 0)
    qseq = _text(hsp_el, "Hsp_qseq") or ""
    hseq = _text(hsp_el, "Hsp_hseq") or ""
    mid = _text(hsp_el, "Hsp_midline") or ""

    identity_pct = round(identity / align_len * 100, 1) if align_len > 0 else 0

    return {
        "score": score,
        "bit_score": bit_score,
        "evalue": evalue,
        "identity": identity,
        "identity_pct": identity_pct,
        "positive": positive,
        "gaps": gaps,
        "alignment_length": align_len,
        "query_from": query_from,
        "query_to": query_to,
        "hit_from": hit_from,
        "hit_to": hit_to,
        "query_alignment": qseq,
        "hit_alignment": hseq,
        "midline": mid,
    }


def _text(el: ET.Element, path: str) -> str:
    found = el.find(path)
    return found.text if found is not None and found.text else ""
