"""Tests that every benchmark ID an engine advertises resolves to a declared
benchmark record in the machine-readable catalog.

An engine that lists a ``benchmarks`` identifier with no record in
``app/data/benchmarks/*.json`` would surface a phantom claim in public
``describe()`` output. These tests keep the catalog and the engines in sync.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.engines import ENGINES
from app.services.benchmarks import load_benchmark_files


def test_every_engine_benchmark_id_resolves_to_catalog():
    catalog_names = {r["name"] for r in load_benchmark_files()}
    dangling: list[tuple[str, str]] = []
    for _name, engine in ENGINES.items():
        for bid in getattr(engine, "benchmarks", None) or []:
            if bid not in catalog_names:
                dangling.append((engine.name, bid))
    assert not dangling, (
        "engine-advertised benchmark IDs missing from the catalog: %r" % dangling
    )