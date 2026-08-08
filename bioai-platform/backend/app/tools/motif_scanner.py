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


# Well-known PROSITE-style patterns. Keys are display names; each entry has a
# human-readable description plus the PROSITE pattern string.
MOTIF_LIBRARY: dict[str, dict[str, str]] = {
    "N-glycosylation site": {
        "description": "Asn-linked glycosylation: N-{P}-[ST]-{P}",
        "pattern": "N-{P}-[ST]-{P}",
    },
    "cAMP/cGMP kinase site": {
        "description": "cAMP/cGMP-dependent protein kinase phosphorylation: [RK]-{2}-x-[ST]",
        "pattern": "[RK]-{2}-x-[ST]",
    },
    "Protein kinase C site": {
        "description": "Protein kinase C phosphorylation: [ST]-x-[RK]",
        "pattern": "[ST]-x-[RK]",
    },
    "Casein kinase II site": {
        "description": "Casein kinase II phosphorylation: [ST]-x(2)-[DE]",
        "pattern": "[ST]-x(2)-[DE]",
    },
    "Tyrosine kinase site": {
        "description": "Tyrosine kinase phosphorylation: [RK]-x(2,3)-[DE]-x(2,3)-Y",
        "pattern": "[RK]-x(2,3)-[DE]-x(2,3)-Y",
    },
    "N-myristoylation site": {
        "description": "Myristyl anchor: G-{EDRKHPFYW}-x(2)-[STAGCN]-{P}",
        "pattern": "G-{EDRKHPFYW}-x(2)-[STAGCN]-{P}",
    },
    "Amidation site": {
        "description": "C-terminal amidation signal: x-G-[RK]-x",
        "pattern": "x-G-[RK]-x",
    },
    "RGD cell-attachment": {
        "description": "Integrin-binding tripeptide: R-G-D",
        "pattern": "R-G-D",
    },
    "ATP/GTP-binding P-loop": {
        "description": "Walker A motif: [AG]-x(4)-G-K-[ST]",
        "pattern": "[AG]-x(4)-G-K-[ST]",
    },
    "C2H2 zinc finger (part)": {
        "description": "Classic zinc finger half: C-x(2,4)-C-x(3)-[LIVMFYWC]-x(8)-H-x(3,5)-H",
        "pattern": "C-x(2,4)-C-x(3)-[LIVMFYWC]-x(8)-H-x(3,5)-H",
    },
    "Leucine zipper": {
        "description": "Heptad repeat: L-x(6)-L-x(6)-L-x(6)-L",
        "pattern": "L-x(6)-L-x(6)-L-x(6)-L",
    },
}


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


def scan_library(sequence: str) -> dict:
    """Scan a protein against the curated PROSITE library."""
    seq = _clean_protein(sequence)
    if not seq:
        raise MotifError("Sequence is empty")
    hits = []
    for name, entry in MOTIF_LIBRARY.items():
        try:
            result = scan_pattern(seq, entry["pattern"])
        except MotifError:
            continue
        if result["count"] > 0:
            hits.append({
                "name": name,
                "description": entry["description"],
                "pattern": entry["pattern"],
                "count": result["count"],
                "matches": result["matches"],
            })
    hits.sort(key=lambda h: (-h["count"], h["name"]))
    return {
        "sequence_type": detect_sequence_type(seq),
        "length": len(seq),
        "patterns_scanned": len(MOTIF_LIBRARY),
        "motifs_found": len(hits),
        "hits": hits,
    }
