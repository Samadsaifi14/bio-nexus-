"""Fixture manifest integrity (BBS-2 §Reproducibility, MATRIX 28 / 29).

Walks benchmark/fixtures/, SHA-256s every tracked file, and maintains
manifests/fixtures_manifest.json. Fails on any drift so committed expected
values can never silently change without the manifest updating too.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"
MANIFEST = FIXTURES / "manifests" / "fixtures_manifest.json"

IGNORE_PARTS = {".git", "__pycache__", "manifests"}
GEN_DIRS = {"results"}  # run records live outside fixtures/ (in benchmark/results)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def walk() -> dict[str, dict]:
    files = {}
    for p in sorted(FIXTURES.rglob("*")):
        if not p.is_file():
            continue
        if any(part in IGNORE_PARTS for part in p.parts):
            continue
        rel = p.relative_to(FIXTURES).as_posix()
        files[rel] = {"sha256": sha256(p), "bytes": p.stat().st_size}
    return files


def main() -> int:
    current = walk()
    manifest = {
        "schema": "bionexus-fixture-manifest/v1",
        "root": "benchmark/fixtures",
        "files": current,
    }
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"fixture manifest: {len(current)} files -> {MANIFEST.relative_to(HERE)}")
    return 0


def check() -> int:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    current = walk()
    drift = []
    for rel in sorted(set(manifest["files"]) | set(current)):
        expected = manifest["files"].get(rel)
        live = current.get(rel)
        if expected is None:
            drift.append(f"+ {rel}")
        elif live is None:
            drift.append(f"- {rel}")
        elif expected["sha256"] != live["sha256"]:
            drift.append(f"~ {rel} sha256 changed")
    if drift:
        print("FIXTURE MANIFEST DRIFT:")
        for line in drift:
            print("  " + line)
        print("rerun `python benchmark/verify_fixtures.py` to refresh the manifest (only after intentional edits).")
        return 1
    print(f"fixture manifest OK ({len(current)} files, no drift)")
    return 0


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "check"
    sys.exit(main() if mode == "regenerate" else check())