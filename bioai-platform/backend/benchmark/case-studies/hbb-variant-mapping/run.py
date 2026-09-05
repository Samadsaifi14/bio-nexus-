"""Executable BioNexus case study: deterministic HBB E7V variant mapping.

This is a reproducibility demonstration, not a clinical diagnostic workflow.
The canonical human beta-globin precursor sequence used here is UniProt
P68871 (HBB_HUMAN).  The substitution is expressed in precursor numbering as
E7V, corresponding to the classic sickle beta-globin substitution.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from app.tools.alignment_insights import alignment_insights

UNIPROT_ACCESSION = "P68871"
SOURCE_NAME = "UniProtKB/Swiss-Prot"
HBB_WILDTYPE = (
    "MVHLTPEEKSAVTALWGKVNVDEVGGEALGRLLVVYPWTQRFFESFGDLSTPDAVMGNPKVKAHGKK"
    "VLGAFSDGLAHLDNLKGTFATLSELHCDKLHVDPENFRLLGNVLVCVLAHHFGKEFTPPVQAAYQKVV"
    "AGVANALAHKYH"
)
VARIANT = {"id": "HBB-E7V", "position": 7, "ref": "E", "alt": "V"}
EXPECTED_WT_SHA256 = "9ebf320eb707d71644444fe5006ed58af56a0bf0ec9568eb6a3a65e0e8191465"
EXPECTED_MUTANT_SHA256 = "5b53af628d9be96c8e95abf0de0f88df7e7e69d330b9e70941443ba3e5f1667d"


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def build_mutant() -> str:
    index = VARIANT["position"] - 1
    observed = HBB_WILDTYPE[index]
    if observed != VARIANT["ref"]:
        raise ValueError(
            f"reference residue mismatch at position {VARIANT['position']}: "
            f"expected {VARIANT['ref']}, observed {observed}"
        )
    return HBB_WILDTYPE[:index] + VARIANT["alt"] + HBB_WILDTYPE[index + 1 :]


def run_case() -> dict:
    mutant = build_mutant()
    wt_sha = sha256_text(HBB_WILDTYPE)
    mutant_sha = sha256_text(mutant)
    if wt_sha != EXPECTED_WT_SHA256 or mutant_sha != EXPECTED_MUTANT_SHA256:
        raise ValueError("sequence checksum mismatch; case-study fixture changed")

    insights = alignment_insights(
        [HBB_WILDTYPE, mutant],
        reference_index=0,
        variants=[VARIANT],
    )
    mapping = insights["variant_mapping"][0]
    column = insights["columns"][VARIANT["position"] - 1]

    if mapping["status"] != "mapped":
        raise ValueError("variant did not map to the reference alignment")
    if mapping["reference_symbol"] != VARIANT["ref"]:
        raise ValueError("mapped reference symbol does not match declared variant")

    return {
        "case_study": "HBB-E7V-variant-mapping",
        "status": "executed",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source": {
            "database": SOURCE_NAME,
            "accession": UNIPROT_ACCESSION,
            "sequence_length": len(HBB_WILDTYPE),
            "sequence_sha256": wt_sha,
            "source_semantics": "reference sequence fixture; accession must be independently revalidated when source releases change",
        },
        "variant": {
            **VARIANT,
            "numbering": "precursor protein numbering",
            "mutant_sequence_sha256": mutant_sha,
        },
        "deterministic_result": {
            "alignment_position": mapping["alignment_position"],
            "reference_symbol": mapping["reference_symbol"],
            "conservation": mapping["conservation"],
            "entropy_bits": mapping["entropy_bits"],
            "column_consensus": column["consensus"],
            "column_logo": column["logo"],
            "alignment_length": insights["alignment_length"],
            "sequence_count": insights["sequence_count"],
            "mean_conservation": insights["mean_conservation"],
            "mean_entropy_bits": insights["mean_entropy_bits"],
        },
        "evidence": {
            "classes": ["reference_retrieval", "deterministic_computation"],
            "claims": [
                {
                    "id": "variant-mapped",
                    "claim": "The declared precursor E7V substitution maps deterministically to alignment position 7 in this ungapped two-sequence comparison.",
                    "evidence_refs": ["UniProt:P68871", "BioNexus:alignment_insights"],
                }
            ],
        },
        "reproducibility": {
            "algorithm": "app.tools.alignment_insights.alignment_insights",
            "fixture_checksums_locked": True,
            "random_seed_required": False,
        },
        "scientific_boundary": (
            "This case demonstrates deterministic sequence provenance and variant mapping only. "
            "It does not establish diagnostic validity, pathogenicity classification, clinical utility, "
            "or superiority over external bioinformatics platforms."
        ),
    }


def main() -> None:
    result = run_case()
    output_path = Path(__file__).with_name("result.json")
    output_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
