"""Count origin is reviewed evidence, never inferred from integer formatting."""
import re
from pydantic import BaseModel, Field
from typing import Literal

from app.rnaseq.expression import RnaSeqExpressionError


class CountOrigin(BaseModel):
    kind: Literal["raw_counts", "salmon"] = "raw_counts"
    normalization: Literal["none", "normalized", "unknown"] = "unknown"
    evidence: str = Field(min_length=10, max_length=2000)
    method: str = Field(min_length=2, max_length=200)
    annotation: str = Field(min_length=2, max_length=500)
    reviewed: bool = False

    def check(self) -> dict:
        if not self.reviewed or self.normalization != "none" or re.search(r"\b(FPKM|RPKM|TPM|CPM)\b", self.method, re.I):
            raise RnaSeqExpressionError("Review count origin and confirm unnormalized counts. Integer values alone do not establish raw counts.")
        return {**self.model_dump(), "count_origin_status": "ANALYST_ATTESTED", "format_valid": True,
                "independently_verified": False}
