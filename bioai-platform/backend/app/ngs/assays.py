"""
Assay identifier / pipeline router (blueprint point 1 & master architecture).

There is no single universal NGS pipeline. The router inspects the input — FASTQ naming,
read metadata, reference target, sample metadata — and classifies it into an assay so the
orchestrator can pick the correct scientific pipeline:

    INPUT -> detect / choose assay ->
        WGS / WES  -> germline ( -> somatic, CNV, SV )
        RNA-seq    -> expression
        Amplicon   -> targeted variants

Each assay maps to its own stage DAG. The detection is explicit and auditable: every decision
records which evidence was used so a user can see WHY their sample was routed a certain way.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class AssayType(str, Enum):
    WGS = "WGS"
    WES = "WES"
    RNA_SEQ = "RNA-seq"
    AMPLICON = "Amplicon"
    UNKNOWN = "Unknown"


class SampleType(str, Enum):
    """Germline vs somatic (tumor/normal) — affects downstream branch & callers."""

    GERMLINE = "germline"
    SOMATIC = "somatic"
    UNKNOWN = "unknown"


class LibraryType(str, Enum):
    PAIRED_END = "paired-end"
    SINGLE_END = "single-end"
    UNKNOWN = "unknown"


@dataclass
class AssayDetection:
    assay: AssayType
    sample_type: SampleType
    library_type: LibraryType
    confidence: float = 0.0          # 0..1
    evidence: list[str] = field(default_factory=list)
    detected_pairs: list[tuple[str, str]] = field(default_factory=list)   # (R1,R2) file names

    def to_dict(self) -> dict:
        return {
            "assay": self.assay.value,
            "sample_type": self.sample_type.value,
            "library_type": self.library_type.value,
            "confidence": round(self.confidence, 3),
            "evidence": self.evidence,
            "pairs": [list(p) for p in self.detected_pairs],
        }


# ---------------------------------------------------------------------------
# FASTQ parsing helpers
# ---------------------------------------------------------------------------


_R1_PATTERNS = [r"_R1", r"_1\(", r"_1\.", r"\.R1", r"R1_", r"\bR1\b"]
_R2_PATTERNS = [r"_R2", r"_2\(", r"_2\.", r"\.R2", r"R2_", r"\bR2\b"]


def _read_end(name: str) -> int:
    """Return 1 for R1, 2 for R2, 0 if unknown, -1 if single/unknown-end unfiltered."""
    for p in _R2_PATTERNS:
        if re.search(p, name, re.IGNORECASE):
            return 2
    for p in _R1_PATTERNS:
        if re.search(p, name, re.IGNORECASE):
            return 1
    return 0


def pair_fastq(files: list[str]) -> tuple[list[tuple[str, str]], list[str]]:
    """Return (paired (R1,R2) tuples, unpaired_files).

    Pairs are matched by stripping the read-end token from the basename, e.g.
        SAMPLE_001_R1.fastq.gz / SAMPLE_001_R2.fastq.gz
    match on 'SAMPLE_001'. Files with no R1/R2 marker are treated as unpaired/single.
    """
    bases: dict[str, dict[int, str]] = {}
    canonical = []
    for f in files:
        stem = re.sub(r"\.(fastq|fq)(\.gz)?$", "", f, flags=re.IGNORECASE)
        end = _read_end(stem)
        key = re.sub(r"_R[12]$", "", stem, flags=re.IGNORECASE)
        canonical.append(key)
        bases.setdefault(key, {})[end] = f

    pairs: list[tuple[str, str]] = []
    singles: list[str] = []
    used: set[str] = set()
    for key in bases:
        ends = bases[key]
        if 1 in ends and 2 in ends:
            pairs.append((ends[1], ends[2]))
            used.add(ends[1])
            used.add(ends[2])
        elif 1 in ends:
            used.add(ends[1])
            singles.append(ends[1])
        elif 2 in ends:
            # An R2 with no matching R1 is a mispairing the orchestrator must flag.
            used.add(ends[2])
            singles.append(ends[2])
        else:
            # No read end marker -> unpaired (could be single-end or a lone sample).
            f = ends.get(1) or ends.get(2)
            if f is None:
                f = bases[key][0] if 0 in bases[key] else None
            if f:
                used.add(f)
                singles.append(f)

    # Any file never assigned to a key above (shouldn't happen, but be safe).
    for f in files:
        stem = re.sub(r"\.(fastq|fq)(\.gz)?$", "", f, flags=re.IGNORECASE)
        key = re.sub(r"_R[12]$", "", stem, flags=re.IGNORECASE)
        if f not in used:
            singles.append(f)
    return pairs, sorted(set(singles))


def sample_id_from_name(name: str) -> str:
    """Derive a stable sample id (strip R1/R2 + extension + compression)."""
    stem = re.sub(r"\.(fastq|fq)(\.gz)?$", "", name, flags=re.IGNORECASE)
    return re.sub(r"_R[12]$", "", stem, flags=re.IGNORECASE)


# ---------------------------------------------------------------------------
# Assay detection
# ---------------------------------------------------------------------------


_AMPLICON_WORDS = ["amplicon", "panel", "targeted", "bait", "hotspot", "16s", "16s-", "amplicons"]
_RNA_WORDS = ["rna", "rnaseq", "rna-seq", "mrna", "cdna", "poly-a", "polya", "exon", "stranded"]
_WES_WORDS = ["wes", "exome", "exon", "targeted-exome", "targeted exome", "whole-exome"]
_WGS_WORDS = ["wgs", "whole-genome", "whole genome", "genome", "dna"]
_SOMATIC_WORDS = ["somatic", "tumor", "tumour", "cancer", "tum", "normal", "germline_tumor"]
_GERMLINE_WORDS = ["germline", "normal", "constitutive", "blood"]
_PE_WORDS = ["paired", "pe", "r1", "r2", "fq1", "fq2", "mate"]
_SE_WORDS = ["single", "se", "sr", "single-end"]


def _score(needle: str, words: list[str]) -> bool:
    n = needle.lower()
    return any(w.lower() in n for w in words)


class AssayRouter:
    """Deterministic, evidence-recording assay classifier."""

    def detect(
        self,
        *,
        files: Optional[list[str]] = None,
        reference: Optional[str] = None,
        metadata: Optional[dict] = None,
        fastq_url: Optional[str] = None,
    ) -> AssayDetection:
        metadata = metadata or {}
        evidence: list[str] = []
        detected_pairs: list[tuple[str, str]] = []
        library = LibraryType.UNKNOWN
        sample_type = SampleType.UNKNOWN

        # 1. Read pairing from file names / metadata
        if files:
            pairs, singles = pair_fastq(files)
            detected_pairs = pairs
            if pairs or library == LibraryType.UNKNOWN:
                if len(pairs) > 0 or any(_score(f, _PE_WORDS) for f in files):
                    library = LibraryType.PAIRED_END
                    evidence.append(f"paired-end ({len(pairs)} pair(s) matched)")
                elif any(_score(f, _SE_WORDS) for f in files):
                    library = LibraryType.SINGLE_END
                    evidence.append("single-end by naming")
        declared = metadata.get("library_type") or metadata.get("library")
        if declared:
            if str(declared).lower() in ("paired", "paired-end", "pe"):
                library = LibraryType.PAIRED_END
            elif str(declared).lower() in ("single", "single-end", "se"):
                library = LibraryType.SINGLE_END

        # 2. Assay from naming + metadata + reference
        assay = AssayType.UNKNOWN
        name_blob = " ".join(files or []) + " " + str(fastq_url or "")
        declared_assay = str(metadata.get("assay", "")).lower()
        declared_ref = str(reference or "").lower()

        if declared_assay in ("wgs", "whole-genome"):
            assay = AssayType.WGS; evidence.append("declared assay=whole-genome")
        elif declared_assay in ("wes", "exome", "whole-exome"):
            assay = AssayType.WES; evidence.append("declared assay=exome")
        elif declared_assay in ("rna-seq", "rnaseq", "rna"):
            assay = AssayType.RNA_SEQ; evidence.append("declared assay=rna-seq")
        elif declared_assay in ("amplicon", "panel", "targeted"):
            assay = AssayType.AMPLICON; evidence.append("declared assay=amplicon/panel")

        if assay == AssayType.UNKNOWN and _score(declared_ref, _RNA_WORDS):
            assay = AssayType.RNA_SEQ; evidence.append("reference suggests RNA-seq")

        if assay == AssayType.UNKNOWN:
            if _score(name_blob, _AMPLICON_WORDS) or _score(declared_ref, _AMPLICON_WORDS):
                assay = AssayType.AMPLICON; evidence.append("amplicon/targeted keywords in input")
            elif _score(name_blob, _WES_WORDS):
                assay = AssayType.WES; evidence.append("exome keywords in input")
            elif _score(name_blob, _RNA_WORDS) or _score(declared_ref, _RNA_WORDS):
                assay = AssayType.RNA_SEQ; evidence.append("RNA keywords in input/reference")
            elif _score(name_blob, _WGS_WORDS) or _score(declared_ref, _WGS_WORDS):
                assay = AssayType.WGS; evidence.append("whole-genome keywords in input/reference")

        # 3. Sample type (germline vs somatic)
        md_samp = str(metadata.get("sample_type", "")).lower()
        if md_samp in ("somatic", "tumor", "tumour", "cancer"):
            sample_type = SampleType.SOMATIC; evidence.append("declared somatic")
        elif md_samp in ("germline", "normal", "blood", "constitutive"):
            sample_type = SampleType.GERMLINE; evidence.append("declared germline")
        elif _score(name_blob, _SOMATIC_WORDS) and not md_samp:
            sample_type = SampleType.SOMATIC; evidence.append("somatic keywords in input")
        elif _score(name_blob, _GERMLINE_WORDS) and not md_samp:
            sample_type = SampleType.GERMLINE; evidence.append("germline keywords in input")

        # 4. Confidence
        confidence = self._confidence(assay, evidence, declared_assay, metadata)

        return AssayDetection(
            assay=assay,
            sample_type=sample_type,
            library_type=library,
            confidence=confidence,
            evidence=evidence or ["no distinguishing evidence; defaulting to generic analysis"],
            detected_pairs=detected_pairs,
        )

    @staticmethod
    def _confidence(assay: AssayType, evidence: list[str], declared: str, metadata: dict) -> float:
        if not evidence:
            return 0.0
        base = 0.5
        if declared:
            base += 0.3
        if "_R1" in " ".join(evidence) or "paired" in " ".join(evidence):
            base += 0.1
        if metadata.get("read_length") or metadata.get("platform"):
            base += 0.1
        return min(base, 1.0)


def detect_assay(
    *,
    files: Optional[list[str]] = None,
    reference: Optional[str] = None,
    metadata: Optional[dict] = None,
    fastq_url: Optional[str] = None,
) -> AssayDetection:
    return AssayRouter().detect(
        files=files, reference=reference, metadata=metadata, fastq_url=fastq_url
    )


def classify_inputs(files: list[str]) -> tuple[AssayType, SampleType, LibraryType, list[tuple[str, str]]]:
    """Convenience wrapper returning the core classification + pairs."""
    det = detect_assay(files=files)
    return det.assay, det.sample_type, det.library_type, det.detected_pairs
