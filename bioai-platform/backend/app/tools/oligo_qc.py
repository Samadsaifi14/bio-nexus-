"""Oligo QC and in-silico PCR helpers for primer design verification.

Implements the checks a wet-lab scientist runs on candidate primers before
ordering them (the IDT OligoAnalyzer + Primer-BLAST + in-silico PCR steps of
the canonical primer design workflow):

  * GC content and salt-adjusted melting temperature
  * Hairpin (intra-molecular stem-loop) prediction
  * Self-dimer / hetero-dimer prediction (complementary annealing)
  * In-silico PCR: where each primer binds in the template, expected amplicon
    length, and specificity (number of binding sites).

Tm and secondary structures use primer3-py thermodynamics with explicit
reaction conditions. Risk thresholds remain screening rules, not PCR validation.
"""

from __future__ import annotations

import math
import re
from typing import Dict, List, Optional, Tuple

_COMP = {ord('A'): 'T', ord('T'): 'A', ord('G'): 'C', ord('C'): 'G',
         ord('N'): 'N', ord('U'): 'A',
         ord('a'): 't', ord('t'): 'a', ord('g'): 'c', ord('c'): 'g',
         ord('n'): 'n', ord('u'): 'a'}

def clean(seq: str) -> str:
    """Upper-case and strip whitespace (and any non-letter junk)."""
    return re.sub(r"[^A-Za-z]", "", seq).upper().replace("U", "T")


def is_dna(seq: str) -> bool:
    s = clean(seq)
    return bool(s) and all(c in "ATGCN" for c in s)


def reverse_complement(seq: str) -> str:
    return seq.upper().translate(_COMP)[::-1]


def gc_content(seq: str) -> float:
    s = clean(seq)
    if not s:
        return 0.0
    return round((s.count("G") + s.count("C")) / len(s) * 100.0, 1)


DEFAULT_CONDITIONS = {"mv_conc": 50.0, "dv_conc": 1.5, "dntp_conc": 0.6, "dna_conc": 50.0, "temp_c": 37.0}


def _engine():
    try:
        import primer3
        return primer3
    except ImportError as exc:
        raise RuntimeError("Primer3 thermodynamics unavailable; install primer3-py. No heuristic fallback is used.") from exc


def _sequence(seq: str) -> str:
    s = clean(seq)
    if not s or set(s) - set("ACGT") or len(s) > 60:
        raise ValueError("Thermodynamic QC requires 1–60 unambiguous DNA bases (A/C/G/T); ambiguous bases are not scored.")
    return s


def _conditions(conditions=None):
    values = {**DEFAULT_CONDITIONS, **(conditions or {})}
    if set(values) != set(DEFAULT_CONDITIONS):
        raise ValueError("Unknown thermodynamic condition")
    if any(not math.isfinite(float(v)) or float(v) < 0 for k, v in values.items() if k != "temp_c"):
        raise ValueError("Concentrations must be finite and non-negative")
    if values["dna_conc"] <= 0 or not -20 <= values["temp_c"] <= 100:
        raise ValueError("DNA concentration must be positive and temperature must be -20 to 100 C")
    return values


def salt_adjusted_tm(seq: str, salt_mm: float = 50.0, conditions=None) -> float:
    """SantaLucia nearest-neighbour Tm from Primer3; concentrations in mM except DNA in nM."""
    c = _conditions(conditions)
    if conditions is None:
        c["mv_conc"] = salt_mm
    kwargs = {k: v for k, v in c.items() if k != "temp_c"}
    return round(_engine().calc_tm(_sequence(seq), **kwargs, tm_method="santalucia", salt_corrections_method="santalucia"), 2)


def _structure(result, conditions):
    # Primer3 returns free energy in cal/mol. Public output uses kcal/mol.
    dg = float(result.dg) / 1000.0
    found = bool(result.structure_found)
    risk = "none" if not found or dg > -3 else "low" if dg > -4.5 else "medium" if dg > -7 else "high"
    return {"dg": round(dg, 3), "dg_units": "kcal/mol", "tm_c": float(result.tm),
            "structure_found": found, "structure": getattr(result, "ascii_structure", "") or "",
            "risk": risk, "risk_model": "Screening thresholds on predicted delta-G: low <= -3, medium <= -4.5, high <= -7 kcal/mol; not experimental PCR validation",
            "conditions": conditions, "engine": "primer3-py", "engine_version": getattr(_engine(), "__version__", "unknown"),
            "note": "Primer3 thermodynamic prediction; PCR efficiency and genome-wide specificity are not established."}


def hairpin_analysis(seq: str, min_stem: int = 4, min_loop: int = 3, conditions=None) -> Dict:
    """Primer3 hairpin thermodynamics (legacy stem arguments do not alter its model)."""
    c = _conditions(conditions)
    return _structure(_engine().calc_hairpin(_sequence(seq), **c, output_structure=True), c)


def dimer_analysis(a: str, b: str, min_stem: int = 4, conditions=None) -> Dict:
    """Primer3 homo/heterodimer thermodynamics, without invented stem coordinates."""
    c = _conditions(conditions)
    pa, pb = _sequence(a), _sequence(b)
    engine = _engine()
    result = engine.calc_homodimer(pa, **c, output_structure=True) if pa == pb else engine.calc_heterodimer(pa, pb, **c, output_structure=True)
    return _structure(result, c)


def find_binding_sites(template: str, primer: str) -> List[int]:
    """All 0-based start positions where `primer` matches `template`."""
    t = clean(template)
    p = clean(primer)
    if not t or not p:
        return []
    return [m.start() for m in re.finditer(r"(?=" + re.escape(p) + r")", t)]


def in_silico_pcr(template: str, left: str, right: str,
                  expected_product: Optional[int] = None,
                  left_expected: Optional[int] = None,
                  right_expected: Optional[int] = None) -> Dict:
    """Simulate the PCR reaction against a template sequence.

    The forward primer binds as-is; the reverse primer (given 5'->3' as
    Primer3 returns it) is the reverse complement of the forward-strand region
    it anneals to. Amplicons are [forward_site, reverse_site + len(right)).
    """
    t = clean(template)
    lseq = clean(left)
    rseq = clean(right)

    left_sites = find_binding_sites(t, lseq)
    right_target = reverse_complement(rseq)
    right_sites = find_binding_sites(t, right_target)

    amplicons: List[Tuple[int, int, int]] = []
    for f in left_sites:
        for r in right_sites:
            end = r + len(rseq)
            if end > f:
                amplicons.append((f, end, end - f))
    amplicons.sort(key=lambda x: x[2])

    specific = len(left_sites) == 1 and len(right_sites) == 1
    primer3_consistent = False
    if left_expected is not None and right_expected is not None and right_expected > 0:
        right_bind = right_expected - len(rseq) + 1
        primer3_consistent = (
            left_expected in left_sites and right_bind in right_sites
        )

    result: Dict = {
        "template_length": len(t),
        "forward_binding_sites": len(left_sites),
        "reverse_binding_sites": len(right_sites),
        "forward_positions": left_sites[:20],
        "reverse_positions": right_sites[:20],
        "specific": specific,
        "amplicons": [{"start": f, "end": e, "length": ln}
                      for f, e, ln in amplicons[:10]],
        "primer3_consistent": primer3_consistent,
        "note": None,
    }

    if expected_product is not None:
        # Primer3 product size == right_pos - left_pos + 1; allow 1 bp slack.
        match = any(abs(a[2] - expected_product) <= 1 for a in amplicons)
        result["matches_product_size"] = match
    else:
        result["matches_product_size"] = None

    if not left_sites and not right_sites:
        result["note"] = "Neither primer binds the template."
    elif not left_sites:
        result["note"] = "Forward primer does not bind the template."
    elif not right_sites:
        result["note"] = "Reverse primer does not bind the template."
    elif not specific:
        result["note"] = ("Multiple binding sites detected — this primer pair "
                          "may amplify off-target products.")
    else:
        result["note"] = "Specific: each primer binds exactly once."
    return result


def oligo_report(seq: str, conditions=None) -> Dict:
    """Nearest-neighbour thermodynamic QC with fully recorded reaction conditions."""
    s = _sequence(seq)
    c = _conditions(conditions)
    tm = salt_adjusted_tm(s, conditions=c)
    return {"sequence": s, "length": len(s), "gc": gc_content(s), "tm_c": tm,
            "tm_50mM": tm if c["mv_conc"] == 50 else None,
            "tm_model": "Primer3 SantaLucia nearest-neighbor with SantaLucia salt correction",
            "conditions": c, "concentration_units": {"mv_conc": "mM", "dv_conc": "mM", "dntp_conc": "mM", "dna_conc": "nM", "temp_c": "C"},
            "hairpin": hairpin_analysis(s, conditions=c), "self_dimer": dimer_analysis(s, s, conditions=c)}
