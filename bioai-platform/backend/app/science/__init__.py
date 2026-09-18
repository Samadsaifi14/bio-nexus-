"""Scientific result contracts and validation-state infrastructure."""

from .result import ScientificResult, ScientificStatus, build_scientific_result, failed_scientific_result

__all__ = [
    "ScientificResult",
    "ScientificStatus",
    "build_scientific_result",
    "failed_scientific_result",
]
