"""Automated codebase documentation generator (Component 17).

Documentation is generated from the same FastAPI application object served by BioNexus.
This removes the old dynamic-import path (which could load arbitrary modules if its input
were ever influenced) and also prevents API documentation from drifting away from the
actual router registration/prefixes in ``app.main``.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi import FastAPI
from app.main import app as production_app

BACKEND = Path(__file__).resolve().parents[1]
DOCS_OUT = BACKEND / "docs"


def _build_app() -> FastAPI:
    """Return the authoritative application whose registered routes are documented."""
    return production_app


def _http_routes(app: FastAPI) -> list[tuple[str, str, str]]:
    rows = []
    for route in app.routes:
        for method in getattr(route, "methods", []) or []:
            if method in {"HEAD", "OPTIONS"}:
                continue
            endpoint = getattr(route, "endpoint", None)
            doc = ((getattr(endpoint, "__doc__", None) or "").strip().splitlines())
            rows.append((method, getattr(route, "path", "/"), doc[0] if doc else ""))
    return sorted(rows, key=lambda row: (row[1], row[0]))


def _api_md(rows: list[tuple[str, str, str]]) -> str:
    lines = [
        "# BioNexus API (automatically generated)",
        "",
        "> Generated from the registered FastAPI application by `scripts/generate_docs.py` — do not edit by hand.",
        "",
    ]
    for method, path, doc in rows:
        lines.append(f"- `{method}` `{path}` — {doc}")
    lines.append("")
    return "\n".join(lines)


def _engines_md() -> str:
    from app.engines import ENGINES

    lines = ["# BioNexus Scientific Engines", "", "> Generated — do not edit by hand.", ""]
    for name in sorted(ENGINES):
        engine = ENGINES[name]
        description = engine.describe()
        lines += [
            f"## {name}",
            "",
            f"- **Version:** {description.get('version')}",
            f"- **Tool:** {description.get('tool')} ({description.get('tool_version') or 'version detected at runtime'})",
            f"- **Databases:** {', '.join(description.get('databases') or [])}",
            f"- **Parameters:** {description.get('parameters')}",
            f"- **Benchmarks:** {', '.join(description.get('benchmarks') or [])}",
            f"- **Exports:** {', '.join(description.get('export_formats') or [])}",
            f"- **Figures:** {', '.join(description.get('figure_formats') or [])}",
            "",
            "- **Citations:**",
            *[f"  - {citation}" for citation in (description.get("citations") or [])],
            "",
        ]
    return "\n".join(lines)


def _datasets_md() -> str:
    from app.services.dataset_library import list_datasets

    lines = ["# Dataset Library", "", "> Generated — do not edit by hand.", ""]
    for dataset in list_datasets():
        lines += [
            f"## {dataset['name']}",
            f"- **Category:** {dataset.get('category')}",
            f"- **Type:** {dataset.get('type')} · date {dataset.get('date')} · version {dataset.get('version')}",
            f"- **Records:** {dataset.get('records_count')}",
            f"- **Description:** {dataset.get('description')}",
            f"- **Citation:** {dataset.get('citation')}",
            "",
        ]
    return "\n".join(lines)


def main() -> int:
    os.makedirs(DOCS_OUT, exist_ok=True)
    app = _build_app()
    rows = _http_routes(app)
    (DOCS_OUT / "API.md").write_text(_api_md(rows), encoding="utf-8")
    (DOCS_OUT / "ENGINES.md").write_text(_engines_md(), encoding="utf-8")
    (DOCS_OUT / "DATASETS.md").write_text(_datasets_md(), encoding="utf-8")
    print(f"documented {len(rows)} registered routes -> docs/API.md, docs/ENGINES.md, docs/DATASETS.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
