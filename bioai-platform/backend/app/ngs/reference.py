"""
Reference registry (blueprint Stage 4 / point 8).

The platform maintains a versioned registry of references instead of letting users pass a
bare genome path. Each reference bundles the artifacts a pipeline needs (FASTA, index, dict,
BWA index, GATK bundle, annotation/VEP cache, population databases) and — crucially — the
genome build, so the system can refuse fundamentally mismatched provenance such as a
GRCh38 BAM aligned against a GRCh37 annotation.

This is deliberately data-driven and free of heavy binaries: the registry describes WHAT a
reference needs so the orchestrator can validate, and (for large human references the dev
environment cannot download) it can still express the contract.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class GenomeBuild(str, Enum):
    GRCH38 = "GRCh38"
    GRCH37 = "GRCh37"
    WUH_COR_1 = "wuhCor1"     # SARS-CoV-2
    OTHER = "other"


@dataclass
class ReferenceArtifact:
    name: str
    present: bool = False


@dataclass
class Reference:
    id: str
    build: GenomeBuild
    description: str
    fa_path: str = ""
    artifacts: list[ReferenceArtifact] = field(default_factory=list)
    species: str = "Homo sapiens"
    bundled: bool = False   # downloaded/local vs. declared-but-unavailable (large human refs)

    def require(self, *names: str) -> "Reference":
        for n in names:
            self.artifacts.append(ReferenceArtifact(name=n))
        return self


_HUMAN_WGS_WES_DECLARED = (
    Reference(id="grch38", build=GenomeBuild.GRCH38, description="Human genome GRCh38 (hg38)")
    .require("GRCh38.fa", "GRCh38.fa.fai", "GRCh38.dict", "BWA index", "GATK bundle", "VEP cache", "gnomAD", "ClinVar")
)
_HUMAN_GRCH37_DECLARED = (
    Reference(id="grch37", build=GenomeBuild.GRCH37, description="Human genome GRCh37 (hg19)")
    .require("GRCh37.fa", "GRCh37.fa.fai", "GRCh37.dict", "BWA index", "GATK bundle", "VEP cache", "gnomAD", "ClinVar")
)


def build_registry() -> dict[str, Reference]:
    return {"grch38": _HUMAN_WGS_WES_DECLARED, "grch37": _HUMAN_GRCH37_DECLARED}


REGISTRY = build_registry()


class BuildMismatch(Exception):
    """Raised when aligned data and annotation do not share a genome build."""


def get_reference(ref_id: str) -> Reference:
    key = ref_id.strip().lower()
    if key in REGISTRY:
        return REGISTRY[key]
    # Aliases
    aliases = {
        "grch38": "grch38", "hg38": "grch38", "hg19": "grch37", "grch37": "grch37",
        "grch37": "grch37", "37": "grch37", "38": "grch38",
    }
    resolved = aliases.get(key)
    if resolved:
        return REGISTRY[resolved]
    raise KeyError(f"Unknown reference '{ref_id}'. Known: {', '.join(REGISTRY)}")


def _coerce_build(build) -> GenomeBuild:
    if isinstance(build, GenomeBuild):
        return build
    s = str(build).strip().upper()
    for cand in GenomeBuild:
        if cand.value.upper() == s:
            return cand
    # aliases
    if s in ("HG38", "HUMAN"):
        return GenomeBuild.GRCH38
    if s in ("HG19", "37"):
        return GenomeBuild.GRCH37
    return GenomeBuild.OTHER


def validate_build_compatibility(
    alignment_build: object,
    annotation_build: object,
) -> tuple[bool, str]:
    """Refuse a fundamentally mismatched provenance (GRCh38 BAM vs GRCh37 annotation).

    Returns (ok, message). A non-ok result must abort the pipeline.
    """
    ab = _coerce_build(alignment_build)
    nb = _coerce_build(annotation_build)
    if ab == nb:
        return True, f"Builds match: {ab.value}"
    msg = (
        f"PROVENANCE ERROR: data aligned to {ab.value} but annotation is "
        f"{nb.value}. These builds are incompatible (different coordinates); "
        f"refusing to continue. Use a matching reference + annotation pair."
    )
    return False, msg


def describe(reference_id: str) -> dict:
    try:
        ref = get_reference(reference_id)
        return {
            "id": ref.id,
            "build": ref.build.value,
            "description": ref.description,
            "species": ref.species,
            "bundled": ref.bundled,
            "artifacts": [{"name": a.name, "present": a.present} for a in ref.artifacts],
        }
    except KeyError:
        return {"id": reference_id, "build": GenomeBuild.OTHER.value, "description": "unknown"}
