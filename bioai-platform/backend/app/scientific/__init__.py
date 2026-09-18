"""Scientific result contract and validation registry for BioNexus.

Every backend scientific module returns a :class:`ScientificResult`.  The
frontend's single non-negotiable rendering rule is: render exactly what the
backend emitted — never invent, recalculate, rename or silently substitute
scientific values.
"""

from .contract import (
    ScientificResult,
    ScientificStatus,
    build_result,
    canonical_json,
    sha256_hex,
)
from .registry import (
    module_validation_state,
    registry_state,
    ValidationState,
)

__all__ = [
    "ScientificResult",
    "ScientificStatus",
    "ValidationState",
    "build_result",
    "canonical_json",
    "sha256_hex",
    "module_validation_state",
    "registry_state",
]