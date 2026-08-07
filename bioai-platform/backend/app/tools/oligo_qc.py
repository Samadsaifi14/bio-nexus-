"""Oligo QC and in-silico PCR helpers for primer design verification.

Implements the checks a wet-lab scientist runs on candidate primers before
ordering them (the IDT OligoAnalyzer + Primer-BLAST + in-silico PCR steps of
the canonical primer design workflow):

  * GC content and salt-adjusted melting temperature
  * Hairpin (intra-molecular stem-loop) prediction
  * Self-dimer / hetero-dimer prediction (complementary annealing)
  * In-silico PCR: where each primer binds in the template, expected amplicon
    length, and specificity (number of binding sites).

These are heuristic approximations suitable for screening. A delta-G is
estimated with a simple nearest-neighbour-style pair score so primers can be
ranked; it is not a substitute for a full NN thermodynamics calculation.
"""

from __future__ import annotations

import math
import re
from typing import Dict, List, Optional, Tuple

_COMP = {ord('A'): 'T', ord('T'): 'A', ord('G'): 'C', ord('C'): 'G',
         ord('N'): 'N', ord('U'): 'A',
         ord('a'): 't', ord('t'): 'a', ord('g'): 'c', ord('c'): 'g',
         ord('n'): 'n', ord('u'): 'a'}

# Per-base-pair stacking energies (kcal/mol) for the complementary stem.
# Only canonical Watson-Crick pairs count towards a stem; wobble pairs are
# ignored so short weak "stems" don't turn every oligo into a dimer/hairpin.
_PAIR_DG = {
    ('A', 'T'): -1.0, ('T', 'A'): -1.0,
    ('G', 'C'): -2.0, ('C', 'G'): -2.0,
}


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


def _pair_energy(a: str, b: str) -> float:
    return _PAIR_DG.get((a, b), _PAIR_DG.get((b, a), 0.0))


def salt_adjusted_tm(seq: str, salt_mm: float = 50.0) -> float:
    """IDT-style melting temperature.

    Uses the classic NN-approximation formula Tm = 64.9 + 41*(nGC - 16.4)/N
    (valid at ~50 mM monovalent salt) plus the SantaLucia salt correction.
    """
    s = clean(seq)
    n = len(s)
    if n < 1:
        return 0.0
    n_gc = s.count("G") + s.count("C")
    tm = 64.9 + 41.0 * (n_gc - 16.4) / n
    if salt_mm != 50.0:
        tm += 16.6 * math.log10(max(salt_mm, 0.01) / 50.0)
    return round(tm, 1)


def _risk_from_dg(dg: float) -> Tuple[str, str]:
    if dg <= -7.0:
        return "high", "Strongly stabilizing — high risk of mis-priming."
    if dg <= -4.5:
        return "medium", "Moderately stabilizing — keep an eye on it."
    if dg <= -3.0:
        return "low", "Weakly stabilizing — unlikely to matter in practice."
    return "none", "No significant structure predicted."


def hairpin_analysis(seq: str, min_stem: int = 4, min_loop: int = 3) -> Dict:
    """Predict the strongest intra-molecular hairpin.

    A hairpin forms when the strand folds so that one arm is the reverse
    complement of the other arm, separated by a loop of at least `min_loop`
    bases: seq[i:i+L] must equal reverse_complement(seq[j:j+L]). Returns
    delta-G, stem length, stem sequence, loop sequence and a risk level.
    """
    s = clean(seq)
    n = len(s)
    best: Optional[Tuple[float, int, int, int]] = None  # (dg, stem_len, i, j)
    for i in range(n):
        for j in range(i + min_stem + min_loop, n):
            # loop = j - (i + L) must stay >= min_loop
            lmax = min(j - i - min_loop, n - j, 10)
            if lmax < min_stem:
                continue
            for L in range(min_stem, lmax + 1):
                dg = 0.0
                ok = True
                for k in range(L):
                    e = _pair_energy(s[i + k], s[j + L - 1 - k])
                    if e == 0.0:
                        ok = False
                        break
                    dg += e
                if ok and (best is None or dg < best[0]):
                    best = (dg, L, i, j)

    if best is None:
        return {"dg": 5.0, "stem_length": 0, "stem": "", "loop": "",
                "risk": "none", "note": "No hairpin structure predicted."}
    dg, stem_len, i, j = best
    stem = s[i:i + stem_len]
    loop = s[i + stem_len:j]
    risk, note = _risk_from_dg(dg)
    return {
        "dg": round(dg, 1),
        "stem_length": stem_len,
        "stem": stem,
        "loop": loop,
        "risk": risk,
        "note": note,
    }


def dimer_analysis(a: str, b: str, min_stem: int = 4) -> Dict:
    """Predict the strongest dimer between two primers.

    A dimer forms where primer `a` anneals antiparallel to primer `b`, i.e.
    where a region of `a` is complementary to a region of reversed `b`. Reports
    the most stabilizing complementary stem, whether the stem involves the 3'
    end of either primer (extension-competent dimers are the dangerous ones
    for PCR), and a risk level.
    """
    pa = clean(a)
    rev_b = clean(b)[::-1]
    n, m = len(pa), len(rev_b)

    best: Optional[Tuple[float, int, int, int]] = None  # (dg, stem_len, i, j)
    for i in range(n):
        for j in range(m):
            k = 0
            dg = 0.0
            while i + k < n and j + k < m:
                e = _pair_energy(pa[i + k], rev_b[j + k])
                if e == 0.0:
                    break
                dg += e
                k += 1
                if k >= 12:
                    break
            if k >= min_stem and (best is None or dg < best[0]):
                best = (dg, k, i, j)

    if best is None:
        return {"dg": 5.0, "stem_length": 0, "stem": "", "involves_a3": False,
                "involves_b3": False, "risk": "none",
                "note": "No significant dimer predicted."}
    dg, stem_len, i, j = best
    stem = pa[i:i + stem_len]
    a3 = (i + stem_len == n)  # stem reaches the 3' end of primer a
    b3 = (j == 0)             # rev_b[0] complements b's 3' terminal base
    risk, note = _risk_from_dg(dg)
    if a3 or b3:
        note = ("3' end involved — extension-competent, more likely to "
                "interfere with PCR. ") + note
    return {
        "dg": round(dg, 1),
        "stem_length": stem_len,
        "stem": stem,
        "involves_a3": a3,
        "involves_b3": b3,
        "risk": risk,
        "note": note,
    }


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


def oligo_report(seq: str) -> Dict:
    """Full QC report for a single primer."""
    s = clean(seq)
    hp = hairpin_analysis(s)
    sd = dimer_analysis(s, s)
    return {
        "sequence": s,
        "length": len(s),
        "gc": gc_content(s),
        "tm_50mM": salt_adjusted_tm(s),
        "hairpin": hp,
        "self_dimer": sd,
    }
