"""Local enrichment reruns from immutable, owner-scoped DESeq2 artifacts."""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path

from app.rnaseq import expression as ex

MAX_ANNOTATION_BYTES = 10 * 1024 * 1024


@dataclass(frozen=True)
class EnrichmentOptions:
    organism: str = "auto"
    database: str = "GO"
    method: str = "ora"
    id_type: str = "auto"
    aliases: bool = True
    database_label: str = ""
    namespace: str = ""

    def validate(self, has_gmt: bool = False, has_mapping: bool = False) -> None:
        if self.database not in {"GO", "GO:BP", "GO:MF", "GO:CC", "CUSTOM"}:
            raise ex.RnaSeqExpressionError("Choose a GO database or custom GMT.")
        if self.method not in {"ora", "ranked_wilcoxon"}:
            raise ex.RnaSeqExpressionError("Choose ORA or ranked Wilcoxon enrichment.")
        if self.id_type not in {"auto", "SYMBOL", "ENSEMBL", "ENSEMBLTRANS", "ENTREZID"}:
            raise ex.RnaSeqExpressionError("Unsupported identifier type.")
        for value in (self.organism, self.database_label, self.namespace):
            if len(value) > 200 or any(ord(c) < 32 for c in value):
                raise ex.RnaSeqExpressionError("Annotation labels must be plain text up to 200 characters.")
        if self.database == "CUSTOM":
            if not has_gmt or not self.database_label.strip() or not self.namespace.strip() or self.organism.strip() in {"", "auto"}:
                raise ex.RnaSeqExpressionError("Custom GMT requires a source/release label, identifier namespace and documented organism.")
        elif self.organism not in {"auto", "human", "mouse"} or has_gmt or has_mapping:
            raise ex.RnaSeqExpressionError("Local GO supports human/mouse. Use custom GMT for another organism or supplied mapping.")


def _download_results(user_id: str, run_id: str, parent: dict) -> bytes:
    entry = next((x for x in parent.get("artifacts", []) if x.get("name") == "deseq2_all_results.tsv"), None)
    if entry is None:
        raise ex.RnaSeqExpressionError("Saved run has no DESeq2 results table. Run DESeq2 first.")
    source_run = entry.get("source_run_id", run_id)
    if not re.fullmatch(r"[0-9a-fA-F-]{36}", source_run):
        raise ex.RnaSeqExpressionError("Invalid source run in saved manifest.")
    # Never retrieve a client URL: the authenticated user's storage prefix is authoritative.
    path = f"{ex._safe_user_key(user_id)}/{source_run}/deseq2_all_results.tsv"
    try:
        data = ex.get_supabase().storage.from_(ex.BUCKET).download(path)
    except Exception as exc:
        raise ex.RnaSeqExpressionError("Saved result table is unavailable for this user.") from exc
    if not isinstance(data, (bytes, bytearray)) or len(data) > ex.MAX_COUNTS_BYTES:
        raise ex.RnaSeqExpressionError("Saved result table is invalid or exceeds the size limit.")
    if hashlib.sha256(data).hexdigest() != entry.get("sha256"):
        raise ex.RnaSeqExpressionError("Saved result checksum mismatch; enrichment was blocked.")
    return bytes(data)


def _execute(results: Path, options: Path, out: Path) -> dict:
    rscript = shutil.which(os.environ.get("BIONEXUS_RSCRIPT", "Rscript"))
    if not rscript:
        raise ex.RnaSeqExpressionError("Rscript is not installed in the backend runtime.")
    try:
        run = subprocess.run([rscript, str(Path(__file__).with_suffix(".R")), str(results), str(options), str(out)],
                             capture_output=True, text=True, timeout=600, check=False)
    except subprocess.TimeoutExpired as exc:
        raise ex.RnaSeqExpressionError("Enrichment exceeded the 600-second limit.") from exc
    if run.returncode:
        lines = (run.stderr or run.stdout).strip().splitlines()
        detail = next((line for line in reversed(lines) if line != "Execution halted"), "R enrichment failed")
        raise ex.RnaSeqExpressionError(detail[:500])
    return json.loads((out / "go_enrichment_summary.json").read_text())


def rerun_enrichment(*, user_id: str, run_id: str, options: EnrichmentOptions,
                     gmt: Path | None = None, mapping: Path | None = None) -> dict:
    options.validate(gmt is not None, mapping is not None)
    for path in (gmt, mapping):
        if path and (path.stat().st_size == 0 or path.stat().st_size > MAX_ANNOTATION_BYTES):
            raise ex.RnaSeqExpressionError("Annotation files must be non-empty and at most 10 MB.")
    parent = ex.load_manifest(user_id, run_id)
    data = _download_results(user_id, run_id, parent)
    new_id = str(uuid.uuid4())
    with tempfile.TemporaryDirectory(prefix="bionexus-enrichment-") as folder:
        root = Path(folder); out = root / "output"; out.mkdir()
        results = root / "results.tsv"; results.write_bytes(data)
        config = {**asdict(options), "alpha": parent["summary"]["alpha"],
                  "gmt_path": str(gmt) if gmt else "", "mapping_path": str(mapping) if mapping else ""}
        config_path = root / "options.json"; config_path.write_text(json.dumps(config))
        enrichment = _execute(results, config_path, out)
        provenance = {**{k: v for k, v in parent.get("provenance", {}).items() if not k.startswith("enrichment_")},
                      "run_id": new_id, "parent_run_id": run_id,
                      "enrichment_options": asdict(options), "enrichment_source_sha256": hashlib.sha256(data).hexdigest(),
                      "enrichment_execution": "Local R; no gene lists sent to external services"}
        for name, path in (("enrichment_gene_sets.gmt", gmt), ("enrichment_id_mapping.tsv", mapping)):
            if path:
                if path.stat().st_size > MAX_ANNOTATION_BYTES:
                    raise ex.RnaSeqExpressionError("Annotation file exceeds 10 MB.")
                shutil.copyfile(path, out / name)
                provenance[name + "_sha256"] = ex.sha256_file(path)
        summary = {**parent["summary"], "enrichment": enrichment}
        (out / "analysis_summary.json").write_text(json.dumps(summary, indent=2))
        (out / "provenance.json").write_text(json.dumps(provenance, indent=2))
        retained = []
        for item in parent["artifacts"]:
            if item["name"].startswith(("go_", "enrichment_")) or item["name"] in {"analysis_summary.json", "provenance.json"}:
                continue
            retained.append({**{k: v for k, v in item.items() if k != "url"}, "source_run_id": item.get("source_run_id", run_id)})
        prefix = f"{ex._safe_user_key(user_id)}/{new_id}"
        for path in sorted(out.iterdir()):
            payload = path.read_bytes(); entry = ex._artifact_entry(path.name, payload)
            ex._upload_bytes(f"{prefix}/{path.name}", payload, entry["content_type"]); retained.append(entry)
        manifest = {"run_id": new_id, "state": "SUCCEEDED", "summary": summary, "provenance": provenance, "artifacts": retained}
        ex._upload_bytes(f"{prefix}/manifest.json", json.dumps(manifest, indent=2).encode(), "application/json")
        return ex._hydrate_manifest(manifest, prefix)
