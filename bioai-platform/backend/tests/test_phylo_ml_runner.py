"""Regression tests for the ML tree runner in app/routers/phylo.py.

The ML path never ran in production: IQ-TREE/PhyML were installed only by the
Dockerfiles, which the host never built, so every ML job died immediately with
"No ML tree tool found" (phylo.py:402). Once the binaries were present, a
second defect surfaced — the result-metadata block still referenced a bare
`bs` that an earlier refactor had renamed to `bs_requested`/`bs_effective`, so
a tree that IQ-TREE had built successfully was thrown away with
"ML tree error: name 'bs' is not defined".

The external binary is stubbed here, so these tests need no IQ-TREE install,
no network, and no DB.
"""

import asyncio
import shutil
import sys
import uuid
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.routers import phylo

ALN_FASTA = (
    ">q1\nMKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQ\n"
    ">q2\nMKTAYIAKQRQISFVKSHFSRQLEERLGLIEVR\n"
    ">q3\nMKTAYIAKQRQIAFVKSHFSRQLEERLGLIEVQ\n"
    ">q4\nMRTAYIAKQRQISFVKSHFSRQLEERLGLIEVQ\n"
)

IQTREE_STATS_TMPL = (
    "IQ-TREE version: 2.3.6\n"
    "{ufboot}"
    "Log-likelihood of the tree: -1234.567890\n"
)


def _iqtree_stats(argv):
    """IQ-TREE only reports a UFBoot run when -bb was actually passed."""
    if "-bb" in argv:
        n = argv[argv.index("-bb") + 1]
        ufboot = f"Ultrafast bootstrap (UFBoot) with {n} iterations\n"
    else:
        ufboot = ""
    return IQTREE_STATS_TMPL.format(ufboot=ufboot)

TREE = "(q1:0.1,(q2:0.05,q3:0.05):0.02,q4:0.1);"


class _FakeProc:
    """Minimal stand-in for asyncio.subprocess.Process."""

    def __init__(self, returncode=0, stderr=b""):
        self.returncode = returncode
        self._stderr = stderr

    async def communicate(self):
        return b"", self._stderr

    def kill(self):
        pass


def _iqtree_exec(captured):
    """Fake create_subprocess_exec that writes the files IQ-TREE would emit."""

    async def _exec(*cmd, **kwargs):
        argv = [str(a) for a in cmd]
        captured["argv"] = argv
        prefix = argv[argv.index("-pre") + 1]
        Path(prefix + ".treefile").write_text(TREE + "\n")
        Path(prefix + ".iqtree").write_text(_iqtree_stats(argv))
        return _FakeProc()

    return _exec


def _phyml_exec(captured):
    async def _exec(*cmd, **kwargs):
        argv = [str(a) for a in cmd]
        captured["argv"] = argv
        aln = argv[argv.index("-i") + 1]
        Path(aln + "_phyml_tree.txt").write_text(TREE + "\n")
        Path(aln + "_phyml_stats.txt").write_text("lnL = -1234.567890\n")
        return _FakeProc()

    return _exec


@pytest.fixture
def job():
    """Register a job so _patch() has somewhere to write, then clean it up."""
    jid = f"test-{uuid.uuid4().hex[:8]}"
    yield jid
    phylo._jobs.pop(jid, None)


@pytest.fixture(autouse=True)
def _no_ai(monkeypatch):
    """The runner calls the AI interpreter after completion; keep tests hermetic."""

    async def _noop(*args, **kwargs):
        return None

    monkeypatch.setattr("app.ai.tool_interpreter.interpret_tool_result", _noop)


def _req(**kw):
    params = dict(
        sequences=[], method="ml", seq_type="protein", model="LG", bootstrap=0
    )
    params.update(kw)
    return phylo.PhyloRequest(**params)


def _install_tools(monkeypatch, iqtree=True, phyml=True):
    monkeypatch.setattr(
        shutil,
        "which",
        lambda name: {
            "iqtree2": "/usr/local/bin/iqtree2" if iqtree else None,
            "iqtree": None,
            "phyml": "/usr/local/bin/phyml" if phyml else None,
        }.get(name),
    )


def test_ml_no_bootstrap_completes_and_records_honest_provenance(
    monkeypatch, job
):
    """bootstrap=0 must yield a real tree, not a NameError.

    This is the exact case that failed in production: `bs` was undefined, the
    except handler turned it into phase="error", and the completed tree was
    discarded.
    """
    _install_tools(monkeypatch)
    captured = {}
    monkeypatch.setattr(
        phylo.asyncio, "create_subprocess_exec", _iqtree_exec(captured)
    )
    phylo._init(job, _req(bootstrap=0))

    asyncio.run(phylo._run_phyml_local(job, ALN_FASTA, _req(bootstrap=0)))

    got = phylo._read(job)
    assert got["phase"] == "complete", got.get("error")
    assert got["newick"] == TREE
    meta = got["meta"]
    assert meta["engine"] == "iqtree2"
    # No bootstrap requested -> no -bb flag, and provenance must say "none"
    assert "-bb" not in captured["argv"]
    assert meta["support"] == "none"
    assert meta["support_detail"] == "No bootstrap requested."
    assert meta["bootstrap_effective"] is None
    assert meta["bootstrap_requested"] == 0


def test_ml_provenance_reports_replicates_actually_run(monkeypatch, job):
    """A sub-1000 request is clamped to 1000 by IQ-TREE; meta must say 1000.

    Reporting the requested 100 here would misstate the evidence actually
    computed, which is the same class of defect as the CASTp false-zero.
    """
    _install_tools(monkeypatch)
    captured = {}
    monkeypatch.setattr(
        phylo.asyncio, "create_subprocess_exec", _iqtree_exec(captured)
    )
    phylo._init(job, _req(bootstrap=100))

    asyncio.run(phylo._run_phyml_local(job, ALN_FASTA, _req(bootstrap=100)))

    got = phylo._read(job)
    assert got["phase"] == "complete", got.get("error")
    assert captured["argv"][captured["argv"].index("-bb") + 1] == "1000"
    assert got["meta"]["bootstrap_requested"] == 100
    assert got["meta"]["bootstrap_effective"] == 1000
    assert "UFBoot" in got["meta"]["support_detail"]


def test_ml_support_detail_never_claims_uncomputed_alrt(monkeypatch, job):
    """No -alrt flag is ever passed, so SH-aLRT must not appear in provenance."""
    _install_tools(monkeypatch)
    captured = {}
    monkeypatch.setattr(
        phylo.asyncio, "create_subprocess_exec", _iqtree_exec(captured)
    )
    phylo._init(job, _req(bootstrap=1000))

    asyncio.run(phylo._run_phyml_local(job, ALN_FASTA, _req(bootstrap=1000)))

    got = phylo._read(job)
    assert got["phase"] == "complete", got.get("error")
    assert "SH-aLRT" not in got["meta"]["support_detail"]
    assert "SH-aLRT" not in str(got["meta"])
    # the label is still parsed from the .iqtree file when UFBoot ran
    assert got["meta"]["support"] == "ultrafast bootstrap 1000"


def test_ml_phyml_fallback_completes(monkeypatch, job):
    """With no IQ-TREE on PATH, PhyML must produce a complete job."""
    _install_tools(monkeypatch, iqtree=False, phyml=True)
    captured = {}
    monkeypatch.setattr(
        phylo.asyncio, "create_subprocess_exec", _phyml_exec(captured)
    )
    phylo._init(job, _req(bootstrap=0))

    asyncio.run(phylo._run_phyml_local(job, ALN_FASTA, _req(bootstrap=0)))

    got = phylo._read(job)
    assert got["phase"] == "complete", got.get("error")
    assert got["newick"] == TREE
    assert got["meta"]["engine"] == "phyml"
    assert got["meta"]["support_detail"] == "No bootstrap requested."
    assert got["meta"]["bootstrap_requested"] == 0


def test_ml_phyml_bootstrap_provenance(monkeypatch, job):
    """PhyML classic bootstrap is reported verbatim (no 1000 clamp)."""
    _install_tools(monkeypatch, iqtree=False, phyml=True)
    captured = {}
    monkeypatch.setattr(
        phylo.asyncio, "create_subprocess_exec", _phyml_exec(captured)
    )
    phylo._init(job, _req(bootstrap=50))

    asyncio.run(phylo._run_phyml_local(job, ALN_FASTA, _req(bootstrap=50)))

    got = phylo._read(job)
    assert got["phase"] == "complete", got.get("error")
    assert captured["argv"][captured["argv"].index("-b") + 1] == "50"
    assert got["meta"]["bootstrap_requested"] == 50
    assert got["meta"]["bootstrap_effective"] == 50
    assert "PhyML" in got["meta"]["support_detail"]


def test_ml_tool_failure_surfaces_stderr(monkeypatch, job):
    """A non-zero exit must report the engine's stderr, not succeed silently."""

    async def _exec(*cmd, **kwargs):
        return _FakeProc(returncode=1, stderr=b"iqtree2: cannot open file")

    _install_tools(monkeypatch)
    monkeypatch.setattr(phylo.asyncio, "create_subprocess_exec", _exec)
    phylo._init(job, _req(bootstrap=0))

    asyncio.run(phylo._run_phyml_local(job, ALN_FASTA, _req(bootstrap=0)))

    got = phylo._read(job)
    assert got["phase"] == "error"
    assert "cannot open file" in got["error"]
    assert got["newick"] is None


def test_ml_no_tree_written_is_not_reported_as_success(monkeypatch, job):
    """Exit 0 but no .treefile must not yield a completed job."""

    async def _exec(*cmd, **kwargs):
        return _FakeProc()

    _install_tools(monkeypatch)
    monkeypatch.setattr(phylo.asyncio, "create_subprocess_exec", _exec)
    phylo._init(job, _req(bootstrap=0))

    asyncio.run(phylo._run_phyml_local(job, ALN_FASTA, _req(bootstrap=0)))

    got = phylo._read(job)
    assert got["phase"] == "error"
    assert "no output tree" in got["error"].lower()
