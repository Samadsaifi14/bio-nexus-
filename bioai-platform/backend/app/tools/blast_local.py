"""Local NCBI BLAST+ against an explicitly provisioned Swiss-Prot snapshot.

No database substitution: comprehensive UniProt/nr and nucleotide requests stay
on their configured providers. A missing local runtime returns None, not zero hits.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from functools import lru_cache

from app.integrations.ncbi.parser import parse_blast_xml

DATABASE_ALIASES = {"swissprot", "uniprotkb_swissprot"}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


@lru_cache(maxsize=4)
def _reference(root: str, manifest_mtime: int) -> dict:
    folder = Path(root).resolve()
    manifest = json.loads((folder / "manifest.json").read_text())
    if manifest.get("database") != "swissprot" or not manifest.get("release"):
        raise ValueError("local BLAST reference lacks database/release identity")
    indexed = manifest.get("index_files") or {}
    if not indexed:
        raise ValueError("local BLAST reference index manifest is empty")
    for name, expected in indexed.items():
        if Path(name).name != name or not name.startswith("swissprot."):
            raise ValueError("invalid BLAST index manifest path")
        path = folder / name
        if path.is_symlink() or _sha256(path) != expected:
            raise ValueError("BLAST reference index checksum mismatch")
    return manifest


def run_local_blast(sequence: str, program: str, database: str, max_hits: int = 100,
                    timeout: int = 120) -> dict | None:
    if program != "blastp" or database not in DATABASE_ALIASES:
        return None
    configured = os.environ.get("BIONEXUS_BLAST_DB_ROOT", "").strip()
    executable = shutil.which("blastp")
    if not configured or not executable:
        return None
    root = Path(configured)
    if not root.is_absolute() or not (root / "manifest.json").is_file():
        return None
    manifest = _reference(str(root), (root / "manifest.json").stat().st_mtime_ns)
    query = re.sub(r"\s+", "", sequence).upper().rstrip("*")
    if not 6 <= len(query) <= 10000 or re.search(r"[^ACDEFGHIKLMNPQRSTVWYBXZJUO]", query):
        return {"error": "Local BLAST requires one protein sequence of 6-10000 residues",
                "hits": [], "count": 0, "search_complete": False}
    maximum = max(1, min(int(max_hits), 100))
    threads = max(1, min(int(os.environ.get("BIONEXUS_BLAST_THREADS", "2")), 4))
    task = "blastp-short" if len(query) < 30 else "blastp"
    with tempfile.TemporaryDirectory(prefix="bionexus-blast-") as temporary:
        fasta = Path(temporary) / "query.fasta"
        output = Path(temporary) / "result.xml"
        fasta.write_text(">query\n" + query + "\n")
        args = [executable, "-query", str(fasta), "-db", str(root / "swissprot"),
                "-task", task, "-outfmt", "5", "-out", str(output),
                "-max_target_seqs", str(maximum), "-evalue", "10",
                "-num_threads", str(threads)]
        if task == "blastp-short":
            args += ["-seg", "no", "-comp_based_stats", "0"]
        try:
            process = subprocess.run(args, capture_output=True, text=True,
                                     timeout=max(1, min(int(timeout), 300)), check=False)
        except subprocess.TimeoutExpired:
            return {"error": "Local BLAST exceeded its execution deadline",
                    "hits": [], "count": 0, "search_complete": False}
        if process.returncode != 0 or not output.is_file():
            raise RuntimeError("Local BLAST executable failed; no completed search was returned")
        xml = output.read_text()
    parsed = parse_blast_xml(xml)
    if "error" in parsed:
        raise ValueError(parsed["error"])
    hits = sorted(parsed["hits"], key=lambda hit: (-hit["bit_score"], hit["evalue"], hit["accession"]))[:maximum]
    return {**parsed, "hits": hits, "count": len(hits), "search_complete": True,
            "source": "local-blast+", "database": "swissprot", "program": program,
            "requested_database": database, "executed_database": "swissprot",
            "database_release": manifest["release"],
            "database_scope": manifest.get("scope"),
            "database_sha256": manifest["fasta_sha256"],
            "reference_manifest_sha256": _sha256(root / "manifest.json"),
            "reference": manifest, "raw_result_xml": xml, "fallback_used": False,
            "parameters": {"program": program, "task": task, "evalue": 10,
                           "max_hits": maximum, "num_threads": threads,
                           "seg": "no" if task == "blastp-short" else "BLAST+ default",
                           "comp_based_stats": 0 if task == "blastp-short" else "BLAST+ default"}}
