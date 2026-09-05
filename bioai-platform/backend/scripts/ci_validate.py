"""CI validation for the Benchmark + Engine registries (Component 7).

Runs in GitHub Actions after the deterministic pytest suite. Kept dependency-free
(no supabase client) so it fails fast on structural drift:

- every catalog benchmark carries required registry fields (incl. C6 depth),
- benchmark names are unique across the catalog,
- every benchmark section is a known result section,
- every registered engine describes() a complete contract,
- every engine-declared benchmark reference exists in the catalog.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.engines import ENGINES
from app.services.benchmarks import _RESULT_SECTIONS, load_benchmark_files

REQUIRED_RECORD_FIELDS = (
    "name", "category", "description", "input", "expected_output",
    "tolerance", "ground_truth", "citation", "source", "stage",
    "difficulty", "version",
)
DESCRIBE_KEYS = (
    "name", "version", "tool", "tool_version", "databases", "parameters",
    "citations", "benchmarks", "export_formats", "figure_formats",
)

# Pipeline result sections plus standalone tool sections used by the catalog.
KNOWN_SECTIONS = set(_RESULT_SECTIONS) | {"primers", "ngs", "docking", "md", "admet"}


def check_catalog() -> list[str]:
    errors: list[str] = []
    records = load_benchmark_files()
    if not records:
        return ["catalog is empty"]
    names: list[str] = []
    for r in records:
        for field in REQUIRED_RECORD_FIELDS:
            if field not in r or r.get(field) is None:
                errors.append(f"{r.get('name', '<unnamed>')}: missing '{field}'")
        if r.get("difficulty") not in {"easy", "medium", "hard"}:
            errors.append(f"{r.get('name')}: bad difficulty {r.get('difficulty')!r}")
        if isinstance(r.get("version"), int) and r["version"] < 1:
            errors.append(f"{r.get('name')}: bad version {r.get('version')}")
        if r.get("section") and r["section"] not in KNOWN_SECTIONS:
            errors.append(f"{r.get('name')}: unknown section {r.get('section')}")
        names.append(r.get("name", ""))
    dups = {n for n in names if names.count(n) > 1}
    if dups:
        errors.append(f"duplicate benchmark names: {sorted(dups)}")
    return errors


def check_engines() -> list[str]:
    errors: list[str] = []
    if not ENGINES:
        return ["engine registry is empty"]
    catalog_names = {r["name"] for r in load_benchmark_files()}
    for name, engine in ENGINES.items():
        if name != engine.name:
            errors.append(f"registry key {name} != engine.name {engine.name}")
        desc = engine.describe()
        for key in DESCRIBE_KEYS:
            if key not in desc:
                errors.append(f"{name}: describe() missing '{key}'")
        if not engine.export_formats or "json" not in engine.export_formats:
            errors.append(f"{name}: json export unsupported")
        for bm in engine.benchmarks:
            if bm not in catalog_names:
                errors.append(f"{name}: benchmark ref '{bm}' not in catalog")
    return errors


def main() -> int:
    errors = check_catalog() + check_engines()
    if errors:
        print("VALIDATION FAILED:")
        for e in errors:
            print(f"  - {e}")
        return 1
    print("VALIDATION OK: catalog + engine registries consistent")
    return 0


if __name__ == "__main__":
    sys.exit(main())