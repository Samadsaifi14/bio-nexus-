"""Engine registry — BioNexus 2.0 Components 4 & 5.

Each engine is an independent module with the same contract
(runner/validator/parser/exporter/citation/figure/benchmark/tests).
New engines register themselves here; the public API reads this registry.
"""

from app.engines.base import BaseEngine, EngineResult, ValidationReport
from app.engines.blast_engine import blast_engine
from app.engines.uniprot_engine import uniprot_engine

ENGINES: dict[str, BaseEngine] = {
    engine.name: engine for engine in (blast_engine, uniprot_engine)
}

__all__ = ["BaseEngine", "EngineResult", "ValidationReport", "ENGINES", "blast_engine", "uniprot_engine"]


def get_engine(name: str) -> BaseEngine | None:
    return ENGINES.get(name)