"""Bounded exact-DNA restriction map; enzyme definitions come from Biopython."""
from __future__ import annotations

import Bio
from Bio import Restriction
from app.tools.sequence_utilities import SequenceUtilitiesError, clean_sequence, reverse_complement_sequence

ENZYME_NAMES = ("EcoRI", "BamHI", "HindIII", "SalI", "XbaI", "XhoI", "NotI", "KpnI", "SmaI", "PstI", "SacI", "BsaI", "BsmBI")


def restriction_map(sequence: str, enzymes: list[str], circular: bool = False) -> dict:
    seq = clean_sequence(sequence, "dna")
    if set(seq) - set("ACGT"):
        raise SequenceUtilitiesError("Restriction maps require unambiguous A/C/G/T DNA; ambiguous bases cannot establish definite sites")
    if len(seq) > 200000:
        raise SequenceUtilitiesError("Restriction map input is limited to 200,000 bases")
    selected = list(dict.fromkeys(enzymes))
    if not selected or len(selected) > len(ENZYME_NAMES) or any(e not in ENZYME_NAMES for e in selected):
        raise SequenceUtilitiesError("Choose supported restriction enzymes: " + ", ".join(ENZYME_NAMES))
    length = len(seq)
    hits, definitions, cuts = [], [], set()
    for name in selected:
        enzyme = getattr(Restriction, name)
        motif = enzyme.site
        definitions.append({"name": name, "recognition": motif, "forward_top_offset": enzyme.fst5, "forward_bottom_offset": len(motif) + enzyme.fst3})
        if len(motif) > length:
            continue
        scan = seq + seq[:len(motif) - 1] if circular else seq
        orientations = [("+", motif)]
        rc = reverse_complement_sequence(motif, "dna")
        if rc != motif:
            orientations.append(("-", rc))
        for strand, recognition in orientations:
            for start in range(length if circular else length - len(motif) + 1):
                if scan[start:start + len(motif)] != recognition:
                    continue
                top = start + enzyme.fst5 if strand == "+" else start - enzyme.fst3
                bottom = start + len(motif) + enzyme.fst3 if strand == "+" else start + len(motif) - enzyme.fst5
                complete = circular or (0 <= top <= length and 0 <= bottom <= length)
                if circular:
                    top, bottom = top % length, bottom % length
                if complete:
                    cuts.add(top)
                hits.append({"enzyme": name, "recognition": recognition, "start": start + 1, "end": ((start + len(motif) - 1) % length) + 1, "strand": strand, "spans_origin": start + len(motif) > length, "top_cut_boundary": top, "bottom_cut_boundary": bottom, "complete_cut": complete})
    ordered = sorted(cuts)
    if circular and ordered:
        fragments = [((ordered[(i + 1) % len(ordered)] - cut) % length) or length for i, cut in enumerate(ordered)]
    elif circular:
        fragments = [length]
    else:
        boundaries = sorted({0, length, *ordered})
        fragments = [b - a for a, b in zip(boundaries, boundaries[1:])]
    hits.sort(key=lambda h: (h["start"], h["enzyme"], h["strand"]))
    return {"length": length, "topology": "circular" if circular else "linear", "enzymes": definitions, "sites": hits, "cut_boundaries": ordered, "fragment_lengths": fragments, "fragment_total": sum(fragments), "product_topology": "circular" if circular and not ordered else "linear", "coordinate_convention": "Recognition start/end: 1-based inclusive. Cleavage boundaries: number of bases before cut on displayed forward strand; 0 is before base 1. Circular boundaries modulo length.", "digest_assumptions": "Complete digestion at supported recognition sites; ignores methylation, star activity, reaction conditions and enzyme efficiency. Fragment lengths use forward-strand cleavage boundaries; overhang bases on the opposite strand may differ.", "provenance": {"source": "Biopython Bio.Restriction curated enzyme definitions", "version": Bio.__version__, "source_url": "https://biopython.org/docs/latest/api/Bio.Restriction.html"}}
