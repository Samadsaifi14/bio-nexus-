"""Count origin is reviewed evidence, never inferred from integer formatting."""
import re
from pydantic import BaseModel, Field
from typing import Literal

from app.rnaseq.expression import RnaSeqExpressionError


class CountOrigin(BaseModel):
    kind: Literal["raw_counts", "salmon"] = "raw_counts"
    classification: Literal["deposited_raw_counts", "verified_count_estimates", "normalized_expression", "unknown_origin"] = "unknown_origin"
    source_uri: str = Field(default="", max_length=2000)
    verification_evidence: str = Field(default="", max_length=2000)
    normalization: Literal["none", "normalized", "unknown"] = "unknown"
    evidence: str = Field(min_length=10, max_length=2000)
    method: str = Field(min_length=2, max_length=200)
    annotation: str = Field(min_length=2, max_length=500)
    reviewed: bool = False

    def check(self) -> dict:
        if len(self.evidence.strip()) < 10 or any(len(value.strip()) < 2 or value.strip().casefold() in {"unknown", "unspecified", "not_declared"} for value in (self.method, self.annotation)):
            raise RnaSeqExpressionError("Supporting count-origin methods and reference annotation must be specified, not blank or unknown.")
        if not self.reviewed or self.normalization != "none" or re.search(r"\b(FPKM|RPKM|TPM|CPM)\b", self.method, re.I):
            raise RnaSeqExpressionError("Review count origin and confirm unnormalized counts. Integer values alone do not establish raw counts.")
        expected = "verified_count_estimates" if self.kind == "salmon" else "deposited_raw_counts"
        if self.classification != expected or len(self.source_uri.strip()) < 4 or self.source_uri.strip().casefold() in {"unknown", "unspecified", "not_declared", "none"}:
            raise RnaSeqExpressionError("Explicit input-provenance classification and a supporting source URI or document identifier are required; normalized and unknown-origin matrices cannot enter DESeq2.")
        if self.kind == "salmon" and len(self.verification_evidence.strip()) < 10:
            raise RnaSeqExpressionError("Count estimates require verification evidence linking original quantifier files to their reference and transcript annotation.")
        return {**self.model_dump(), "count_origin_status": "ANALYST_ATTESTED", "format_valid": True,
                "classification_basis": "reviewed_source_documentation",
                "independently_verified": False}
