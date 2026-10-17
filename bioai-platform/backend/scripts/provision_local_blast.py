"""Provision a complete official Swiss-Prot snapshot for local BLAST+.

The two release-label reads guard against a release changing during download.
All source and index bytes are fingerprinted; requests cannot provide URLs.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import urllib.request

BASE = "https://ftp.uniprot.org/pub/databases/uniprot/current_release/knowledgebase/complete/"


def digest(path):
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def download(name, target):
    if name == "reldate.txt":
        response = urllib.request.urlopen(
            "https://ftp.uniprot.org/pub/databases/uniprot/current_release/knowledgebase/complete/reldate.txt",
            timeout=120,
        )
    elif name == "uniprot_sprot.fasta.gz":
        response = urllib.request.urlopen(
            "https://ftp.uniprot.org/pub/databases/uniprot/current_release/knowledgebase/complete/uniprot_sprot.fasta.gz",
            timeout=120,
        )
    else:
        raise ValueError("Only the two fixed official Swiss-Prot resources may be downloaded")
    with response as source, target.open("wb") as out:
        shutil.copyfileobj(source, out)
    return target


def provision(root):
    root = Path(root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    (root / "manifest.json").unlink(missing_ok=True)
    before = download("reldate.txt", root / "reldate.before.txt").read_text()
    archive = download("uniprot_sprot.fasta.gz", root / "uniprot_sprot.fasta.gz")
    after = download("reldate.txt", root / "reldate.txt").read_text()
    if before != after:
        raise RuntimeError("UniProt release changed during reference download")
    match = re.search(r"(20\d\d_\d\d)", after)
    if not match:
        raise RuntimeError("Could not establish the UniProt reference release")
    fasta = root / "swissprot.fasta"
    with gzip.open(archive, "rb") as source, fasta.open("wb") as out:
        shutil.copyfileobj(source, out)
    with fasta.open("rb") as handle:
        count = sum(line.startswith(b">sp|") for line in handle)
    if count < 100000:
        raise RuntimeError("Downloaded source is not a complete Swiss-Prot snapshot")
    process = subprocess.run(["makeblastdb", "-in", str(fasta), "-dbtype", "prot",
        "-parse_seqids", "-out", str(root / "swissprot"), "-title", "UniProtKB/Swiss-Prot " + match.group(1)],
        check=True, capture_output=True, text=True, timeout=600)
    index_files = {path.name: digest(path) for path in sorted(root.glob("swissprot.*"))
                   if path.name != "swissprot.fasta" and path.is_file()}
    manifest = {"database": "swissprot", "release": match.group(1),
        "scope": "complete UniProtKB/Swiss-Prot canonical sequence snapshot",
        "source_url": BASE + "uniprot_sprot.fasta.gz",
        "release_url": BASE + "reldate.txt", "release_text": after,
        "retrieved_at": datetime.now(timezone.utc).isoformat(), "sequence_count": count,
        "archive_sha256": digest(archive), "fasta_sha256": digest(fasta),
        "index_files": index_files,
        "indexer": subprocess.run(["makeblastdb", "-version"], capture_output=True,
                                 text=True, check=True, timeout=15).stdout.strip()}
    (root / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    archive.unlink()
    fasta.unlink()
    (root / "reldate.before.txt").unlink()
    print(json.dumps(manifest, sort_keys=True))
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("root")
    provision(parser.parse_args().root)
