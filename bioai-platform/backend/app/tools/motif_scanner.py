"""Local protein motif scanner.

Implements the two scanning modes a bench biologist uses to find short
functional motifs in a protein:

  * Custom PROSITE patterns (e.g. ``[ST]-x-[RK]``, ``N-{P}-[ST]-{P}``) parsed
    into a Python regular expression and matched against the query.
  * A curated library of well-known eukaryotic motif patterns (glycosylation,
    phosphorylation, myristoylation, zinc fingers, the P-loop, ...).

Pure local computation — no network calls. This is the "scan your sequence
for motifs" workflow that PROSITE/ScanProsite expose as a web service.
"""

from __future__ import annotations

import re

from app.services.sequence_utils import detect_sequence_type


class MotifError(ValueError):
    pass


# Well-known PROSITE-style patterns, organized by biological category.
#   accession    — PROSITE entry (PSxxxxx) when the pattern maps to a real
#                  curated PROSITE profile; "" for consensus motifs that are
#                  commonly used but not part of the PROSITE database.
#   specificity  — "high" for rare, low-false-positive patterns (zinc fingers,
#                  P-loop, active sites); "loose" for short, high-frequency
#                  consensus sites (most phosphorylation/glycosylation sites).
#   category     — groups patterns for the UI: PTM / DNA binding / RNA binding
#                  / Catalytic / Signal & targeting / Structural.
MOTIF_LIBRARY: dict[str, dict[str, str]] = {
    # --- Post-translational modifications --------------------------------
    "N-glycosylation site": {
        "accession": "PS00001",
        "category": "PTM",
        "specificity": "high",
        "description": "Asn-linked glycosylation: N-{P}-[ST]-{P}",
        "pattern": "N-{P}-[ST]-{P}",
    },
    "Tyrosine sulfation site": {
        "accession": "PS00003",
        "category": "PTM",
        "specificity": "loose",
        "description": "Tyrosine sulfation consensus: [ED]-x(2)-[DE]-x(2)-Y",
        "pattern": "[ED]-x(2)-[DE]-x(2)-Y",
    },
    "cAMP/cGMP kinase site": {
        "accession": "PS00004",
        "category": "PTM",
        "specificity": "loose",
        "description": "cAMP/cGMP-dependent protein kinase phosphorylation: [RK]-{2}-x-[ST]",
        "pattern": "[RK]-{2}-x-[ST]",
    },
    "Protein kinase C site": {
        "accession": "PS00005",
        "category": "PTM",
        "specificity": "loose",
        "description": "Protein kinase C phosphorylation: [ST]-x-[RK]",
        "pattern": "[ST]-x-[RK]",
    },
    "Casein kinase II site": {
        "accession": "PS00006",
        "category": "PTM",
        "specificity": "loose",
        "description": "Casein kinase II phosphorylation: [ST]-x(2)-[DE]",
        "pattern": "[ST]-x(2)-[DE]",
    },
    "Tyrosine kinase site": {
        "accession": "PS00007",
        "category": "PTM",
        "specificity": "loose",
        "description": "Tyrosine kinase phosphorylation: [RK]-x(2,3)-[DE]-x(2,3)-Y",
        "pattern": "[RK]-x(2,3)-[DE]-x(2,3)-Y",
    },
    "N-myristoylation site": {
        "accession": "PS00008",
        "category": "PTM",
        "specificity": "loose",
        "description": "Myristyl anchor: G-{EDRKHPFYW}-x(2)-[STAGCN]-{P}",
        "pattern": "G-{EDRKHPFYW}-x(2)-[STAGCN]-{P}",
    },
    "Amidation site": {
        "accession": "PS00009",
        "category": "PTM",
        "specificity": "loose",
        "description": "C-terminal amidation signal: x-G-[RK]-x",
        "pattern": "x-G-[RK]-x",
    },
    # --- DNA binding ------------------------------------------------------
    "C2H2 zinc finger": {
        "accession": "PS00028",
        "category": "DNA binding",
        "specificity": "high",
        "description": "Classic zinc finger half: C-x(2,4)-C-x(3)-[LIVMFYWC]-x(8)-H-x(3,5)-H",
        "pattern": "C-x(2,4)-C-x(3)-[LIVMFYWC]-x(8)-H-x(3,5)-H",
    },
    "Leucine zipper": {
        "accession": "PS00029",
        "category": "DNA binding",
        "specificity": "loose",
        "description": "Heptad repeat dimerization: L-x(6)-L-x(6)-L-x(6)-L",
        "pattern": "L-x(6)-L-x(6)-L-x(6)-L",
    },
    "Nuclear hormone receptor C4 finger": {
        "accession": "PS00030",
        "category": "DNA binding",
        "specificity": "high",
        "description": "C4 zinc finger of steroid hormone receptors: C-x(2)-C-x(13)-C-x(2)-C",
        "pattern": "C-x(2)-C-x(13)-C-x(2)-C",
    },
    # --- RNA binding ------------------------------------------------------
    "RNP-1 RNA-binding region": {
        "accession": "PS00031",
        "category": "RNA binding",
        "specificity": "high",
        "description": "RNP-1 motif of RNA-recognition proteins: [RK]-G-{P}-[FY]-{V}-x-[FYWH]-[LIVMFY]",
        "pattern": "[RK]-G-{P}-[FY]-{V}-x-[FYWH]-[LIVMFY]",
    },
    # --- Catalytic / nucleotide binding ----------------------------------
    "ATP/GTP-binding P-loop": {
        "accession": "PS00017",
        "category": "Catalytic",
        "specificity": "high",
        "description": "Walker A / P-loop: [AG]-x(4)-G-K-[ST]",
        "pattern": "[AG]-x(4)-G-K-[ST]",
    },
    "Protein kinase ATP-binding": {
        "accession": "PS00107",
        "category": "Catalytic",
        "specificity": "high",
        "description": "Protein kinase ATP-binding signature: [LIVMFYC]-x-[HY]-x-D-[LIVMFY]-K-x(2)-N-[LIVMFYCT]",
        "pattern": "[LIVMFYC]-x-[HY]-x-D-[LIVMFY]-K-x(2)-N-[LIVMFYCT]",
    },
    "Serine protease active site": {
        "accession": "PS00138",
        "category": "Catalytic",
        "specificity": "high",
        "description": "Chymotrypsin-family catalytic Ser: [LIVMFYWC]-G-[HYW]-S-[LIVMFYWC]-G-x(2)-[SAG]",
        "pattern": "[LIVMFYWC]-G-[HYW]-S-[LIVMFYWC]-G-x(2)-[SAG]",
    },
    "Aspartic protease active site": {
        "accession": "PS00141",
        "category": "Catalytic",
        "specificity": "high",
        "description": "Aspartic protease catalytic Asp: [LIVMFGAC]-[LIVMTADN]-[LIVFSA]-D-[STAG]-G-[STAV]-[STAPDENQ]-x(2)-[LIVMFSTNC]-x-[LIVMFGTA]",
        "pattern": "[LIVMFGAC]-[LIVMTADN]-[LIVFSA]-D-[STAG]-G-[STAV]-[STAPDENQ]-x(2)-[LIVMFSTNC]-x-[LIVMFGTA]",
    },
    # --- Signal & targeting -----------------------------------------------
    "Nuclear localization signal (NLS)": {
        "accession": "",
        "category": "Signal & targeting",
        "specificity": "loose",
        "description": "Monopartite NLS consensus: K-[RK]-x(2)-[KRA]",
        "pattern": "K-[RK]-x(2)-[KRA]",
    },
    "ER retention signal": {
        "accession": "",
        "category": "Signal & targeting",
        "specificity": "loose",
        "description": "C-terminal endoplasmic-reticulum retention: [KRHQSA]-[DENQ]-E-L>",
        "pattern": "[KRHQSA]-[DENQ]-E-L>",
    },
    "Secretory signal peptide": {
        "accession": "",
        "category": "Signal & targeting",
        "specificity": "loose",
        "description": "Hydrophobic N-terminal core of a cleavable signal peptide: M-x-[LIVMF]-x(3)-[LIVMF]",
        "pattern": "M-x-[LIVMF]-x(3)-[LIVMF]",
    },
    # --- Structural / adhesion --------------------------------------------
    "RGD cell-attachment": {
        "accession": "PS00016",
        "category": "Structural",
        "specificity": "high",
        "description": "Integrin-binding tripeptide: R-G-D",
        "pattern": "R-G-D",
    },
}

CATEGORY_ORDER = ["PTM", "DNA binding", "RNA binding", "Catalytic", "Signal & targeting", "Structural"]


def list_motif_categories() -> list[str]:
    """Return the ordered list of pattern categories present in the library."""
    return [c for c in CATEGORY_ORDER if any(e["category"] == c for e in MOTIF_LIBRARY.values())]


def get_motif_patterns() -> list[dict]:
    """Return the full library as a list (for presets / API listings)."""
    return [
        {
            "name": name,
            "accession": entry["accession"],
            "category": entry["category"],
            "specificity": entry["specificity"],
            "description": entry["description"],
            "pattern": entry["pattern"],
        }
        for name, entry in MOTIF_LIBRARY.items()
    ]


def prosite_to_regex(pattern: str) -> str:
    """Translate a PROSITE pattern string into a Python regular expression.

    Supported syntax: ``-`` (separator, ignored), ``x`` (any residue),
    ``[AC]`` (one of), ``{ED}`` (none of), ``x(4)`` / ``x(2,4)``
    (repetition), ``<`` (N-terminus) and ``>`` (C-terminus).
    """
    pattern = (pattern or "").strip()
    if not pattern:
        raise MotifError("Pattern is empty")
    i = 0
    n = len(pattern)
    out: list[str] = []

    def consume_repeat() -> None:
        nonlocal i
        if i < n and pattern[i] == "(":
            j = pattern.find(")", i + 1)
            if j == -1:
                raise MotifError(f"Unterminated repeat quantifier at position {i}")
            quant = pattern[i + 1:j]
            if not re.fullmatch(r"\d+(,\d+)?", quant):
                raise MotifError(f"Invalid repeat quantifier ({quant}) at position {i}")
            out.append("{" + quant + "}")
            i = j + 1

    while i < n:
        c = pattern[i]
        if c == "-":
            i += 1
        elif c == "<":
            out.append("^")
            i += 1
        elif c == ">":
            out.append("$")
            i += 1
        elif c == "[":
            j = pattern.find("]", i + 1)
            if j == -1:
                raise MotifError(f"Unterminated '[' group at position {i}")
            group = pattern[i + 1:j]
            if not group or any(ch not in "ACDEFGHIKLMNPQRSTVWY" for ch in group):
                raise MotifError(f"Invalid residue group [{group}] at position {i}")
            out.append("[" + group + "]")
            i = j + 1
            consume_repeat()
        elif c == "{":
            j = pattern.find("}", i + 1)
            if j == -1:
                raise MotifError(f"Unterminated '{{' group at position {i}")
            group = pattern[i + 1:j]
            if not group or any(ch not in "ACDEFGHIKLMNPQRSTVWY" for ch in group):
                raise MotifError(f"Invalid exclusion group {{{group}}} at position {i}")
            out.append("[^" + group + "]")
            i = j + 1
            consume_repeat()
        elif c in ("x", "X"):
            out.append("[A-Z]")
            i += 1
            consume_repeat()
        elif c in "ACDEFGHIKLMNPQRSTVWY":
            out.append(c)
            i += 1
            consume_repeat()
        else:
            raise MotifError(f"Unsupported symbol {c!r} at position {i}")
    return "".join(out)


def _clean_protein(seq: str) -> str:
    return "".join(ch for ch in seq.upper() if ch.isalpha())


def scan_pattern(sequence: str, pattern: str) -> dict:
    """Scan a protein for a single PROSITE pattern."""
    seq = _clean_protein(sequence)
    if not seq:
        raise MotifError("Sequence is empty")
    regex_src = prosite_to_regex(pattern)
    try:
        regex = re.compile(regex_src)
    except re.error as e:
        raise MotifError(f"Pattern compiles to an invalid regular expression: {e}")
    matches = []
    for m in regex.finditer(seq):
        matches.append({
            "start": m.start() + 1,
            "end": m.end(),
            "motif": m.group(0),
        })
    return {
        "sequence_type": detect_sequence_type(seq),
        "pattern": pattern,
        "regex": regex_src,
        "count": len(matches),
        "matches": matches,
    }


def scan_library(sequence: str, categories: list[str] | None = None) -> dict:
    """Scan a protein against the curated PROSITE library.

    ``categories`` optionally restricts the scan to a subset of categories
    (e.g. ``["PTM", "DNA binding"]``). Unknown category names are ignored.
    """
    seq = _clean_protein(sequence)
    if not seq:
        raise MotifError("Sequence is empty")
    allowed = set(categories or [])
    scanned = 0
    hits = []
    for name, entry in MOTIF_LIBRARY.items():
        if allowed and entry["category"] not in allowed:
            continue
        scanned += 1
        try:
            result = scan_pattern(seq, entry["pattern"])
        except MotifError:
            continue
        if result["count"] > 0:
            hits.append({
                "name": name,
                "accession": entry["accession"],
                "category": entry["category"],
                "specificity": entry["specificity"],
                "description": entry["description"],
                "pattern": entry["pattern"],
                "count": result["count"],
                "matches": result["matches"],
            })
    hits.sort(key=lambda h: (-h["count"], h["name"]))
    return {
        "sequence_type": detect_sequence_type(seq),
        "length": len(seq),
        "patterns_scanned": scanned,
        "motifs_found": len(hits),
        "hits": hits,
    }
