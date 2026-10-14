"""Exact primer binding on a supplied DNA template; no genome specificity inference."""
from __future__ import annotations

import hashlib
from Bio.Seq import Seq
from app.tools.sequence_utilities import SequenceUtilitiesError, clean_sequence


def primer_binding_map(sequence: str, forward: str, reverse: str, circular: bool = False,
                       min_product: int = 1, max_product: int = 200000) -> dict:
    seq, fwd, rev = [clean_sequence(s, "dna") for s in (sequence, forward, reverse)]
    if any(set(s) - set("ACGT") for s in (seq, fwd, rev)):
        raise SequenceUtilitiesError("Exact primer maps require unambiguous A/C/G/T template and primers")
    n = len(seq)
    if n > 200000 or not 4 <= len(fwd) <= 200 or not 4 <= len(rev) <= 200:
        raise SequenceUtilitiesError("Template limit is 200,000 bases; primer lengths must be 4–200 bases")
    if max(len(fwd), len(rev)) > n:
        raise SequenceUtilitiesError("Primers cannot be longer than the template")
    if not 1 <= min_product <= max_product <= 200000:
        raise SequenceUtilitiesError("Product bounds must satisfy 1 ≤ minimum ≤ maximum ≤ 200,000")
    sites = []
    for label, primer in (("forward", fwd), ("reverse", rev)):
        for strand, motif in ((1, primer), (-1, str(Seq(primer).reverse_complement()))):
            scan = seq + seq[:len(primer) - 1] if circular else seq
            pos = scan.find(motif)
            while pos >= 0 and pos < n:
                sites.append({"primer": label, "strand": strand, "start": pos + 1,
                              "end": (pos + len(primer) - 1) % n + 1,
                              "spans_origin": pos + len(primer) > n,
                              "three_prime_position": (pos + len(primer) - 1) % n + 1 if strand == 1 else pos + 1})
                if len(sites) > 200:
                    raise SequenceUtilitiesError("More than 200 exact binding orientations; use a less repetitive template or longer primers")
                pos = scan.find(motif, pos + 1)
    products = []
    # Both physical orientations are possible even if the user labels a primer 'forward'.
    for plus_label, minus_label in (("forward", "reverse"), ("reverse", "forward")):
        plus_len = len(fwd if plus_label == "forward" else rev)
        minus_len = len(fwd if minus_label == "forward" else rev)
        for plus in (s for s in sites if s["primer"] == plus_label and s["strand"] == 1):
            for minus in (s for s in sites if s["primer"] == minus_label and s["strand"] == -1):
                start, right = plus["start"] - 1, minus["start"] - 1
                distance = (right - start) % n if circular else right - start
                size = distance + minus_len
                # Exclude overlapping annealing sites and multi-turn circular products.
                if distance < plus_len or size > n or not min_product <= size <= max_product:
                    continue
                product = (seq + seq)[start:start + size] if circular else seq[start:start + size]
                products.append({"start": start + 1, "end": (start + size - 1) % n + 1,
                                 "length": size, "spans_origin": start + size > n,
                                 "plus_primer": plus_label, "minus_primer": minus_label,
                                 "sha256": hashlib.sha256(product.encode()).hexdigest()})
                if len(products) > 100:
                    raise SequenceUtilitiesError("More than 100 candidate products; narrow the size range or use more specific primers")
    sites.sort(key=lambda s: (s["start"], s["primer"], s["strand"]))
    products.sort(key=lambda p: (p["start"], p["length"], p["plus_primer"]))
    return {"length": n, "topology": "circular" if circular else "linear", "sites": sites,
            "products": products, "template_sha256": hashlib.sha256(seq.encode()).hexdigest(),
            "primers": {"forward": fwd, "reverse": rev},
            "coordinate_convention": "1-based inclusive coordinates on the displayed forward strand. Strand +1 extends toward increasing coordinates; -1 extends toward decreasing coordinates. Circular start > end spans the origin.",
            "assumptions": "Exact full-length annealing only, with non-overlapping inward-facing sites from different primers. Circular products span at most one template turn and are linear PCR candidates. No mismatches, 5-prime tails, genome-wide specificity, thermodynamic suitability or experimental amplification inferred.",
            "diagnostics": [] if products else ["No inward-facing exact primer pair meets the selected product bounds."]}
