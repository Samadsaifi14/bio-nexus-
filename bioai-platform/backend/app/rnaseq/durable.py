"""Owner-scoped statistical queue on an explicitly mounted persistent volume.

SQLite transactions serialize claims. Workers heartbeat leases and can resume
bounded attempts after a restart. API processes never start a worker implicitly.
Use one shared local volume (not NFS) for API and worker containers.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import threading
import time
import uuid
from dataclasses import asdict
from contextlib import contextmanager
from pathlib import Path

from app.rnaseq.expression import (ExpressionParameters, RnaSeqExpressionError,
    execute_expression_analysis, expression_readiness, load_manifest, sha256_file, R_SCRIPT)

LEASE_SECONDS = 120
MAX_ATTEMPTS = 3


def root() -> Path:
    value = os.environ.get("BIONEXUS_EXPRESSION_ROOT", "")
    if not value or not Path(value).is_absolute() or str(Path(value).resolve()).startswith(("/tmp/", "/var/tmp/")):
        raise RnaSeqExpressionError("Durable expression storage is unavailable: configure an absolute persistent BIONEXUS_EXPRESSION_ROOT outside /tmp.")
    path = Path(value).resolve()
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    return path


@contextmanager
def db():
    connection = sqlite3.connect(root() / "queue.sqlite", timeout=15, isolation_level=None)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("""CREATE TABLE IF NOT EXISTS jobs (
        id TEXT PRIMARY KEY, owner TEXT NOT NULL, state TEXT NOT NULL,
        phase TEXT NOT NULL, payload TEXT NOT NULL, result TEXT, error TEXT,
        attempts INTEGER NOT NULL DEFAULT 0, lease TEXT, heartbeat REAL,
        created REAL NOT NULL, updated REAL NOT NULL)""")
    connection.execute("CREATE TABLE IF NOT EXISTS workers (id TEXT PRIMARY KEY, heartbeat REAL NOT NULL)")
    try:
        yield connection
    finally:
        if connection.in_transaction:
            connection.rollback()
        connection.close()


def owner_key(user: str) -> str:
    return hashlib.sha256(user.encode()).hexdigest()


def readiness(salmon: bool = False) -> dict:
    status = expression_readiness(salmon)
    try:
        with db() as connection:
            active = connection.execute("SELECT 1 FROM workers WHERE heartbeat > ? LIMIT 1", (time.time() - 30,)).fetchone()
        if not active:
            status["missing"].append("dedicated expression worker heartbeat")
    except (RnaSeqExpressionError, OSError, sqlite3.Error) as exc:
        status["missing"].append(str(exc))
    status["available"] = not status["missing"]
    return status


def enqueue(user: str, counts: Path, metadata: Path, params: ExpressionParameters,
            source: dict, *, input_kind: str = "raw_counts", extras: dict[str, bytes] | None = None) -> dict:
    status = readiness(input_kind == "salmon")
    if not status["available"]:
        raise RnaSeqExpressionError("Durable execution unavailable: " + ", ".join(status["missing"]))
    params.validate()
    job_id = str(uuid.uuid4())
    folder = root() / job_id
    folder.mkdir(mode=0o700)
    try:
        shutil.copyfile(counts, folder / "counts.tsv")
        shutil.copyfile(metadata, folder / "metadata.tsv")
        for name, body in (extras or {}).items():
            if Path(name).name != name:
                raise RnaSeqExpressionError("Invalid prepared input filename")
            (folder / name).write_bytes(body)
        if input_kind == "salmon":
            # Prepared manifest uses portable basenames; only the worker writes absolute paths.
            import csv, io
            rows = list(csv.DictReader(io.StringIO((folder / "counts.tsv").read_text()), delimiter="\t"))
            text = io.StringIO(); writer = csv.writer(text, delimiter="\t", lineterminator="\n")
            writer.writerow(["sample", "quant_file"])
            for row in rows:
                name = row["quant_file"]
                if Path(name).name != name or not (folder / name).is_file():
                    raise RnaSeqExpressionError("Quantification manifest refers to an absent file")
                writer.writerow([row["sample"], str(folder / name)])
            (folder / "counts.tsv").write_text(text.getvalue())
        checksums = {p.name: sha256_file(p) for p in folder.iterdir() if p.is_file()}
        payload = {"params": asdict(params), "source": source, "input_kind": input_kind, "checksums": checksums, "engine_sha256": sha256_file(R_SCRIPT)}
        now = time.time()
        (folder / "owner.txt").write_text(user)
        (folder / "owner.txt").chmod(0o600)
        with db() as connection:
            connection.execute("INSERT INTO jobs (id,owner,state,phase,payload,created,updated) VALUES (?,?, 'QUEUED','qc',?,?,?)",
                               (job_id, owner_key(user), json.dumps(payload), now, now))
    except Exception:
        shutil.rmtree(folder)
        raise
    return {"job_id": job_id, "state": "QUEUED"}


def _owned(connection, job_id: str, user: str):
    row = connection.execute("SELECT * FROM jobs WHERE id=? AND owner=?", (job_id, owner_key(user))).fetchone()
    if not row:
        raise FileNotFoundError("Expression job not found")
    return row


def status(job_id: str, user: str) -> dict:
    with db() as connection:
        row = _owned(connection, job_id, user)
    result = json.loads(row["result"]) if row["result"] else None
    if result:
        digest = result.get("checkpoint_sha256")
        result = load_manifest(user, result["run_id"])
        if digest:
            result["checkpoint_sha256"] = digest
    return {"job_id": job_id, "state": row["state"], "phase": row["phase"],
            "attempts": row["attempts"], "error": row["error"], "result": result}


def approve(job_id: str, user: str, checkpoint_sha256: str) -> dict:
    with db() as connection:
        connection.execute("BEGIN IMMEDIATE")
        row = _owned(connection, job_id, user)
        if row["state"] != "QC_REVIEW":
            raise RnaSeqExpressionError("This job is not awaiting QC review")
        path = root() / job_id / json.loads(row["result"])["checkpoint_file"]
        recorded = json.loads(row["result"])["checkpoint_sha256"]
        if checkpoint_sha256 != recorded or sha256_file(path) != recorded:
            raise RnaSeqExpressionError("QC checkpoint changed; inference cannot proceed")
        payload = json.loads(row["payload"])
        payload["qc_review"] = {"checkpoint_sha256": recorded, "reviewed_at": time.time(),
                                "qc_run_id": json.loads(row["result"])["run_id"],
                                "checkpoint_file": json.loads(row["result"])["checkpoint_file"]}
        connection.execute("UPDATE jobs SET state='QUEUED', phase='infer', attempts=0, payload=?, updated=? WHERE id=?",
                           (json.dumps(payload), time.time(), job_id))
        connection.commit()
    return {"job_id": job_id, "state": "QUEUED"}


def claim(worker_id: str) -> dict | None:
    now = time.time()
    with db() as connection:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute("UPDATE jobs SET state=CASE WHEN attempts < ? THEN 'QUEUED' ELSE 'FAILED' END, error='Worker lease expired', lease=NULL WHERE state='RUNNING' AND heartbeat < ?",
                           (MAX_ATTEMPTS, now - LEASE_SECONDS))
        row = connection.execute("SELECT * FROM jobs WHERE state='QUEUED' AND attempts < ? ORDER BY created LIMIT 1", (MAX_ATTEMPTS,)).fetchone()
        if not row:
            connection.commit(); return None
        lease = str(uuid.uuid4())
        connection.execute("UPDATE jobs SET state='RUNNING', lease=?, heartbeat=?, attempts=attempts+1, error=NULL, updated=? WHERE id=?",
                           (lease, now, now, row["id"]))
        connection.commit()
    return {**dict(row), "lease": lease}


def tick(worker_id: str, job: dict | None = None) -> None:
    with db() as connection:
        connection.execute("INSERT OR REPLACE INTO workers VALUES (?,?)", (worker_id, time.time()))
        if job:
            connection.execute("UPDATE jobs SET heartbeat=? WHERE id=? AND lease=? AND state='RUNNING'", (time.time(), job["id"], job["lease"]))


def run_job(job: dict) -> None:
    folder = root() / job["id"]
    payload = json.loads(job["payload"])
    result = None
    state = "FAILED"
    error = None
    try:
        if sha256_file(R_SCRIPT) != payload["engine_sha256"]:
            raise RnaSeqExpressionError("Statistical implementation changed; submit a new reviewed run")
        for name, digest in payload["checksums"].items():
            if sha256_file(folder / name) != digest:
                raise RnaSeqExpressionError("Retained input checksum mismatch")
        checkpoint = folder / (f"qc_{job['lease']}.rds" if job["phase"] == "qc" else payload["qc_review"]["checkpoint_file"])
        if job["phase"] == "infer" and sha256_file(checkpoint) != payload["qc_review"]["checkpoint_sha256"]:
            raise RnaSeqExpressionError("Reviewed QC checkpoint checksum mismatch")
        result = execute_expression_analysis(user_id=(folder / "owner.txt").read_text(),
            counts_path=folder / "counts.tsv", metadata_path=folder / "metadata.tsv",
            params=ExpressionParameters(**payload["params"]), source_label="reviewed-recovery",
            source_metadata={**payload["source"], "input_checksums": payload["checksums"], "qc_review": payload.get("qc_review")},
            stage=job["phase"], checkpoint_path=checkpoint, input_kind=payload["input_kind"],
            tx2gene_path=folder / "tx2gene.tsv" if payload["input_kind"] == "salmon" else None)
        if job["phase"] == "qc":
            result["checkpoint_sha256"] = sha256_file(checkpoint)
            result["checkpoint_file"] = checkpoint.name
            state = "QC_REVIEW"
        else:
            state = "SUCCEEDED"
    except Exception as exc:
        error = str(exc)[:1000]
        # Invalid scientific inputs do not retry; infrastructure interruptions can.
        if not isinstance(exc, RnaSeqExpressionError) and job["attempts"] + 1 < MAX_ATTEMPTS:
            state = "QUEUED"
    with db() as connection:
        connection.execute("UPDATE jobs SET state=?,result=?,error=?,updated=?,lease=NULL WHERE id=? AND lease=?",
                           (state, json.dumps(result) if result else None, error, time.time(), job["id"], job["lease"]))


def main() -> None:
    os.umask(0o077)
    worker_id = str(uuid.uuid4())
    while True:
        tick(worker_id)
        job = claim(worker_id)
        if not job:
            time.sleep(3); continue
        done = threading.Event()
        def heartbeat():
            while not done.wait(10):
                tick(worker_id, job)
        thread = threading.Thread(target=heartbeat, daemon=True); thread.start()
        try:
            run_job(job)
        finally:
            done.set(); thread.join()


if __name__ == "__main__":
    main()
