"""Milestone 1+2 — Experiment Manager, Provenance Graph, Benchmark repository.

Tests exercise the service layer against a fake Supabase client (no network)
plus an end-to-end _execute wiring test proving a completed pipeline registers
an experiment, records provenance nodes, and finalizes the record.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict

import pytest

from app.services import benchmarks as bench_svc
from app.services import experiment as exp_svc
from app.services import provenance as prov_svc


# ---------------------------------------------------------------------------
# Fake Supabase client — chainable, in-memory, no network.
# ---------------------------------------------------------------------------

class _Resp:
    def __init__(self, data):
        self.data = data


class _Table:
    def __init__(self, sb, name):
        self._sb = sb
        self._name = name
        self._filters = {}
        self._limit = None
        self._order = None
        self._op = "select"
        self._payload = None
        self._conflict = None

    def insert(self, row):
        self._op, self._payload = "insert", row
        return self

    def upsert(self, row, on_conflict=None):
        self._op, self._payload, self._conflict = "upsert", row, on_conflict
        return self

    def update(self, payload):
        self._op, self._payload = "update", payload
        return self

    def select(self, *_cols):
        self._op = "select"
        return self

    def eq(self, col, val):
        self._filters[col] = val
        return self

    def order(self, col, **kw):
        self._order = (col, bool(kw.get("desc", False)))
        return self

    def limit(self, n):
        self._limit = n
        return self

    def execute(self):
        rows = self._sb._rows[self._name]
        if self._op == "insert":
            row = dict(self._payload)
            row.setdefault("id", f"{self._name}-{len(rows) + 1}")
            rows.append(row)
            return _Resp([row])
        if self._op == "upsert":
            row = dict(self._payload)
            keys = self._conflict.split(",") if self._conflict else []
            keys = [k.strip() for k in keys]
            for existing in rows:
                matches = existing.get("id") == row.get("id")
                if not matches and keys:
                    matches = all(existing.get(k) == row.get(k) for k in keys)
                if matches:
                    existing.update(row)
                    row = existing
                    break
            else:
                row.setdefault("id", f"{self._name}-{len(rows) + 1}")
                rows.append(row)
            return _Resp([row])
        if self._op == "update":
            for r in rows:
                for k, v in self._payload.items():
                    r[k] = v
            return _Resp(rows)

        filtered = list(rows)
        if self._filters:
            filtered = [r for r in filtered if all(r.get(k) == v for k, v in self._filters.items())]
        if self._order:
            col, desc = self._order
            filtered.sort(key=lambda r: (r.get(col) is None, r.get(col)))
            if desc:
                filtered.reverse()
        if self._limit:
            filtered = filtered[: self._limit]
        return _Resp(filtered)


class FakeSupabase:
    def __init__(self):
        self._rows = defaultdict(list)

    def table(self, name):
        return _Table(self, name)

    def _seed(self, name, rows):
        self._rows[name].extend([dict(r) for r in rows])


@pytest.fixture
def fake_sb(monkeypatch):
    sb = FakeSupabase()
    monkeypatch.setattr(prov_svc, "get_supabase", lambda: sb)
    monkeypatch.setattr(exp_svc, "get_supabase", lambda: sb)
    monkeypatch.setattr(bench_svc, "get_supabase", lambda: sb)
    return sb


# ---------------------------------------------------------------------------
# Experiment Manager
# ---------------------------------------------------------------------------

class TestExperimentManager:
    def test_begin_writes_immutable_row_and_returns_bnx_id(self, fake_sb):
        exp_id = exp_svc.begin_experiment("job-1", "MKWVTFISLL", "protein_analysis")
        assert exp_id and exp_id.startswith("BNX-")
        rows = fake_sb._rows["experiments"]
        assert len(rows) == 1
        assert rows[0]["job_id"] == "job-1"
        assert rows[0]["status"] == "running"
        assert rows[0]["input_hash"]  # fingerprint written once
        assert rows[0]["pipeline"] == "protein_analysis"

    def test_rejects_empty_input(self, fake_sb):
        assert exp_svc.begin_experiment("", "MKWVTFISLL", "protein_analysis") is None
        assert exp_svc.begin_experiment("job-2", "", "protein_analysis") is None
        assert not fake_sb._rows["experiments"]

    def test_deterministic_seed_reproducible(self, fake_sb):
        a = exp_svc.deterministic_seed("MGHHHH", {"fast_mode": True})
        b = exp_svc.deterministic_seed("MGHHHH", {"fast_mode": True})
        c = exp_svc.deterministic_seed("MGHHHH", {"fast_mode": False})
        assert a == b
        assert a != c

    def test_deterministic_seed_fits_postgres_bigint(self, fake_sb):
        # Regression: seed must never overflow a signed 64-bit bigint column
        # (Postgres max is 2^63-1). The masking above guarantees it.
        bigint_max = (1 << 63) - 1
        for seq in ["MGHHHH", "FVNQHLCGSHLVEALYLVCGERGFFYTPKT", "MKWVTFISLL" * 5, "A" * 2000]:
            for params in (None, {"fast_mode": True}, {"blast_params": {"database": "nr"}}):
                seed = exp_svc.deterministic_seed(seq, params)
                assert 0 <= seed <= bigint_max

    def test_fingerprint_fields(self, fake_sb):
        fp = exp_svc.build_fingerprint("MGHHHH", {"fast_mode": True})
        assert "git_commit" in fp
        assert "software_versions" in fp
        assert "container_hash" in fp
        assert "environment" in fp
        assert fp["random_seed"] == exp_svc.deterministic_seed("MGHHHH", {"fast_mode": True})

    def test_finalize_only_mutates_status(self, fake_sb):
        exp_svc.begin_experiment("job-3", "MKWVTFISLL", "protein_analysis")
        exp_svc.finalize_experiment("job-3", "failed", error="boom")
        row = fake_sb._rows["experiments"][0]
        assert row["status"] == "failed"
        assert row["error"] == "boom"
        assert row["input_hash"]  # immutable fingerprint never cleared

    def test_get_experiment_returns_provenance(self, fake_sb):
        exp_id = exp_svc.begin_experiment("job-4", "MKWVTFISLL", "protein_analysis")
        prov_svc.record_step(exp_id, "blast", tool="BLAST", deps=[], evidence={"count": 1})
        exp = exp_svc.get_experiment("job-4")
        assert exp is not None
        assert exp["experiment_id"] == exp_id
        assert len(exp["provenance"]) == 1
        assert exp["provenance"][0]["node_id"] == "blast"


# ---------------------------------------------------------------------------
# Provenance Graph
# ---------------------------------------------------------------------------

class TestProvenance:
    def test_record_step_upserts_on_node_id(self, fake_sb):
        exp_id = "BNX-20260101-aaaa1111"
        prov_svc.record_step(exp_id, "blast", tool="BLAST", deps=[], evidence={"count": 3})
        prov_svc.record_step(exp_id, "blast", tool="BLAST", deps=[], evidence={"count": 5})
        rows = fake_sb._rows["experiment_steps"]
        assert len(rows) == 1  # upsert replaced, not duplicated
        assert rows[0]["evidence"] == {"count": 5}

    def test_trace_builds_nodes_and_edges(self, fake_sb):
        exp_id = "BNX-20260101-bbbb2222"
        prov_svc.record_step(exp_id, "blast", tool="BLAST", deps=[], evidence={})
        prov_svc.record_step(exp_id, "uniprot", tool="UniProt", deps=["blast"], evidence={})
        exp_svc.begin_experiment("job-5", "MKWVTFISLL", "protein_analysis")
        fake_sb._rows["experiments"][0]["experiment_id"] = exp_id
        trace = prov_svc.trace_for_job("job-5", None)
        assert trace["experiment_id"] == exp_id
        assert {n["id"] for n in trace["nodes"]} == {"blast", "uniprot"}
        assert {"from": "blast", "to": "uniprot"} in trace["edges"]

    def test_trace_missing_job_returns_empty(self, fake_sb):
        trace = prov_svc.trace_for_job("no-such-job", None)
        assert trace["nodes"] == [] and trace["edges"] == []

    def test_record_pipeline_provenance_builds_dag_from_context(self, fake_sb):
        context = {
            "sequence": "MKWVTFISLL",
            "blast": {
                "database": "swissprot", "program": "blastp",
                "count": 1,
                "top_hit": {"accession": "P02768", "description": "albumin"},
            },
            "uniprot": {"accession": "P02768", "organism": "Homo sapiens", "resolved_uniprot": True},
            "pathway_enrichment": {"pathways": [{"name": "Platelet degranulation", "stId": "R-HSA-114608"}]},
            "interpret": {"interpretation": "serum albumin"},
        }
        prov_svc.record_pipeline_provenance("BNX-20260101-cccc3333", context)
        nodes = {r["node_id"]: r for r in fake_sb._rows["experiment_steps"]}
        assert set(nodes) == {"blast", "uniprot", "pathway_enrichment", "interpret"}
        assert nodes["uniprot"]["deps"] == ["blast"]
        assert nodes["pathway_enrichment"]["deps"] == ["blast"]
        assert nodes["blast"]["evidence"]["top_hit"] == "P02768"
        # Only the ones actually present in context get recorded.
        assert "msa" not in nodes and "phylo" not in nodes and "domains" not in nodes


# ---------------------------------------------------------------------------
# Benchmark repository
# ---------------------------------------------------------------------------

class TestBenchmarks:
    def test_compare_metric_numeric_tolerance(self, fake_sb):
        assert bench_svc.compare_metric(95.0, 95.2, 0.5)
        assert not bench_svc.compare_metric(90.0, 95.0, 0.5)
        assert bench_svc.compare_metric("P02768", "P02768", 0)
        assert bench_svc.compare_metric("P02768", "P02769", 0) is False
        assert bench_svc.compare_metric(None, 95, 0) is False

    def test_load_catalog_reads_seed_files(self, fake_sb):
        records = bench_svc.load_benchmark_files()
        assert len(records) >= 15
        categories = {r["category"] for r in records}
        assert {"protein_blast", "dna_blast", "uniprot_retrieval", "structure_retrieval"} <= categories

    def test_seed_upserts_by_category_and_name(self, fake_sb):
        count = bench_svc.seed_benchmarks()
        assert count == len(fake_sb._rows["benchmarks"])
        assert count > 0
        # Re-seeding must not duplicate (unique category+name).
        count2 = bench_svc.seed_benchmarks()
        assert len(fake_sb._rows["benchmarks"]) == count
        assert count2 == count

    def test_run_benchmark_passes_when_context_matches(self, fake_sb):
        fake_sb._seed("benchmarks", [{
            "id": "benchtop", "category": "protein_blast", "name": "P02768 identity",
            "section": "blast",
            "expected_output": {"top_hit_accession": "P02768", "top_hit_identity": 100.0},
            "tolerance": {"top_hit_accession": 0, "top_hit_identity": 0.5},
        }])
        fake_sb._seed("jobs", [{
            "id": "job-bench",
            "context_json": {"blast": {"top_hit": {"accession": "P02768", "identity_pct": 99.9}, "count": 42}},
        }])
        summary = bench_svc.run_benchmark("benchtop", "job-bench")
        assert summary["status"] == "passed"
        assert summary["passed_checks"]["top_hit_identity"] is True
        assert len(fake_sb._rows["benchmark_runs"]) == 1

    def test_run_benchmark_fails_on_mismatch_and_missing(self, fake_sb):
        fake_sb._seed("benchmarks", [{
            "id": "b2", "category": "protein_blast", "name": "wrong",
            "section": "blast",
            "expected_output": {"top_hit_accession": "P99999"},
            "tolerance": {"top_hit_accession": 0},
        }])
        fake_sb._seed("jobs", [{
            "id": "job-bench2",
            "context_json": {"blast": {"top_hit": {"accession": "P02768"}}},
        }])
        s = bench_svc.run_benchmark("b2", "job-bench2")
        assert s["status"] == "failed"
        assert s["passed_checks"]["top_hit_accession"] is False
        # Missing job context -> error status, never a silent pass.
        missing = bench_svc.run_benchmark("b2", "ghost-job")
        assert missing["status"] == "error"

    def test_run_benchmark_prefers_storage_result_over_params(self, fake_sb, monkeypatch):
        # Worker jobs store only params in context_json; the real result is in
        # the storage artifact. The runner must read storage, not the params.
        import app.services.artifact_storage as art

        fake_sb._seed("benchmarks", [{
            "id": "b3", "category": "protein_blast", "name": "storage case",
            "section": "blast",
            "expected_output": {"top_hit_accession": "P01308", "top_hit_identity": 100.0},
            "tolerance": {"top_hit_accession": 0, "top_hit_identity": 1.0},
        }])
        fake_sb._seed("jobs", [{
            "id": "job-worker",
            "context_json": {"sequence": "MALWMRLL", "database": "swissprot", "max_hits": 100},
            "storage_url": "gs://job-artifacts/job-worker/context.json",
        }])
        monkeypatch.setattr(
            art, "download_json",
            lambda url: {
                "sequence": "MALWMRLL",
                "blast": {"top_hit": {"accession": "P01308", "identity_pct": 100.0}, "count": 1},
            },
        )
        s = bench_svc.run_benchmark("b3", "job-worker")
        assert s["status"] == "passed"

    def test_run_benchmark_uses_inline_result_context_when_present(self, fake_sb):
        # Wizard jobs write the full result into context_json directly.
        fake_sb._seed("benchmarks", [{
            "id": "b4", "category": "protein_blast", "name": "inline case",
            "section": "blast",
            "expected_output": {"top_hit_accession": "P04637"},
            "tolerance": {"top_hit_accession": 0},
        }])
        fake_sb._seed("jobs", [{
            "id": "job-wizard",
            "context_json": {
                "blast": {"top_hit": {"accession": "P04637"}, "count": 1},
                "uniprot": {"accession": "P04637"},
            },
        }])
        s = bench_svc.run_benchmark("b4", "job-wizard")
        assert s["status"] == "passed"

    def test_batch_summary_counts_by_status(self, fake_sb):
        fake_sb._seed("benchmark_runs", [
            {"status": "passed", "passed_checks": {}},
            {"status": "passed", "passed_checks": {}},
            {"status": "failed", "passed_checks": {}},
        ])
        summary = bench_svc.batch_summary()
        assert summary["total_runs"] == 3
        assert summary["passed"] == 2
        assert summary["failed"] == 1


# ---------------------------------------------------------------------------
# _execute wiring — a completed run registers + records + finalizes.
# ---------------------------------------------------------------------------

class TestExecuteWiring:
    @pytest.fixture
    def mocks(self, monkeypatch):
        import app.routers.pipeline_v2 as pv

        calls = {"begin": 0, "record": 0, "finalize": 0, "finalized": None, "recorded_with": None}

        def fake_begin(job_id, sequence, pipeline, parameters=None):
            calls["begin"] += 1
            return "BNX-20260101-deadbeef"

        def fake_record(exp_id, context):
            calls["record"] += 1
            calls["recorded_with"] = (exp_id, context)

        def fake_finalize(job_id, status, error=None):
            calls["finalize"] += 1
            calls["finalized"] = (job_id, status, error)

        monkeypatch.setattr("app.services.experiment.begin_experiment", fake_begin)
        monkeypatch.setattr("app.services.provenance.record_pipeline_provenance", fake_record)
        monkeypatch.setattr("app.services.experiment.finalize_experiment", fake_finalize)

        async def fake_blast(*a, **k):
            return {"count": 1, "hits": [{"accession": "P02768"}],
                    "top_hit": {"accession": "P02768", "description": "albumin"}, "source": "ebi"}

        async def fake_uniprot(*a, **k):
            return {"accession": "P02768", "resolved_uniprot": True}

        async def fake_msa(*a, **k):
            return {"aln_fasta": ">x\nMKT", "phylotree": "((A,B)C);"}

        async def fake_pathway(*a, **k):
            return {"pathways": [{"name": "P1", "stId": "R-HSA-1"}]}

        async def fake_domains(*a, **k):
            return {"domains": [{"accession": "IPR000001", "source_db": "interpro"}]}

        async def fake_alphafold(*a, **k):
            return {"structure_available": True, "source": "alphafold_db"}

        async def fake_interpret(*a, **k):
            return {"interpretation": "serum albumin"}

        async def fake_finalize_context(job_id, context):
            context["final_report"] = "done"

        monkeypatch.setattr(pv, "_run_blast", fake_blast)
        monkeypatch.setattr(pv, "_run_uniprot", fake_uniprot)
        monkeypatch.setattr(pv, "_run_msa", fake_msa)
        monkeypatch.setattr(pv, "_run_pathway_enrichment", fake_pathway)
        monkeypatch.setattr(pv, "_run_domains_or_denovo", fake_domains)
        monkeypatch.setattr(pv, "_run_alphafold_or_esmfold", fake_alphafold)
        monkeypatch.setattr(pv, "_run_interpret", fake_interpret)
        monkeypatch.setattr(pv, "_finalize_context", fake_finalize_context)
        monkeypatch.setattr(pv, "_persist_v2_final", lambda *a, **k: None)
        return calls

    def test_execute_complete_path_hooks_fire(self, mocks):
        import asyncio as _asyncio
        import app.routers.pipeline_v2 as pv

        async def run():
            await pv._execute(
                "job-mock",
                "MKWVTFISLL",
                list(pv.STEP_ORDER),
                status_callback=None,
                fast_mode=False,
                blast_params={},
            )

        _asyncio.run(run())
        c = mocks
        assert c["begin"] == 1
        assert c["record"] == 1
        assert c["recorded_with"][0] == "BNX-20260101-deadbeef"
        assert c["recorded_with"][1]["uniprot"]["accession"] == "P02768"
        assert c["finalized"][0] == "job-mock"
        assert c["finalized"][1] == "complete"

    def test_execute_failure_path_finalizes_failed(self, mocks):
        import asyncio as _asyncio
        import app.routers.pipeline_v2 as pv
        from app.routers import pipeline_v2 as pv_mod

        async def run():
            await pv._execute(
                "job-mock-fail",
                "GATTACAGATTACA",
                list(pv.STEP_ORDER),
                status_callback=None,
                fast_mode=False,
                blast_params={},
            )

        # Force a fatal BLAST step failure (DNA query with zero matches → the
        # "failed" terminal path, since de-novo mode is protein-only).
        async def _no_hits_blast(*a, **k):
            return {"count": 0, "error": "no hits", "hits": [], "top_hit": None}

        pv_mod._run_blast = _no_hits_blast

        _asyncio.run(run())
        assert mocks["begin"] == 1
        assert mocks["finalize"] >= 1