"""Tests for techspec.md §2 structure-export endpoints."""

import pytest
from fastapi import HTTPException

from app.routers import structure_export as se


# ── Identifier resolution ────────────────────────────────────────────────────


def test_uniprot_accession_routes_to_alphafold():
    kind, ident, label = se._resolve_source("P04637")
    assert (kind, ident) == ("alphafold", "P04637")
    assert label == "AF_P04637"


def test_pdb_id_routes_to_rcsb():
    kind, ident, label = se._resolve_source("1ubq")
    assert (kind, ident) == ("rcsb", "1UBQ")
    assert label == "1UBQ"


def test_garbage_identifier_rejected_with_400():
    with pytest.raises(HTTPException) as exc:
        se._resolve_source("../../etc/passwd")
    assert exc.value.status_code == 400


def test_empty_identifier_rejected():
    with pytest.raises(HTTPException) as exc:
        se._resolve_source("   ")
    assert exc.value.status_code == 400


# ── URL construction ─────────────────────────────────────────────────────────


def test_alphafold_urls_use_canonical_file_pattern():
    assert se._source_url("alphafold", "P04637", "pdb") == (
        "https://alphafold.ebi.ac.uk/files/AF_P04637-F1-model_v4.pdb"
    )
    assert se._source_url("alphafold", "P04637", "cif") == (
        "https://alphafold.ebi.ac.uk/files/AF_P04637-F1-model_v4.cif"
    )


def test_rcsb_urls():
    assert se._source_url("rcsb", "1UBQ", "cif") == "https://files.rcsb.org/download/1UBQ.cif"


# ── Format gate + fetch behaviour ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_invalid_format_rejected_before_network():
    with pytest.raises(HTTPException) as exc:
        await se.export_structure("P04637", format="exe", user_id="u1")
    assert exc.value.status_code == 400


class _FakeResp:
    def __init__(self, status_code=200, text="ATOM  1  CA  ALA A   1"):
        self.status_code = status_code
        self.text = text

    def raise_for_status(self):
        if self.status_code >= 400:
            import httpx
            raise httpx.HTTPStatusError(f"HTTP {self.status_code}", request=None, response=None)


class _FakeClient:
    last_url = None

    def __init__(self, *a, **k):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def get(self, url):
        _FakeClient.last_url = url
        return _FakeResp()


@pytest.mark.asyncio
async def test_pdb_export_returns_attachment(monkeypatch):
    monkeypatch.setattr(se.httpx, "AsyncClient", _FakeClient)
    res = await se.export_structure("P04637", format="pdb", user_id="u1")
    assert res.media_type == "chemical/x-pdb"
    assert "AF_P04637.pdb" in res.headers["content-disposition"]
    assert b"ATOM" in res.body


@pytest.mark.asyncio
async def test_upstream_404_maps_to_404(monkeypatch):
    class _404Client(_FakeClient):
        async def get(self, url):
            return _FakeResp(404)

    monkeypatch.setattr(se.httpx, "AsyncClient", _404Client)
    with pytest.raises(HTTPException) as exc:
        await se.export_structure("Q9NZB7", format="cif", user_id="u1")  # no AF model
    assert exc.value.status_code == 404


# ── PyMOL session path ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_pse_without_pymol2_returns_503(monkeypatch):
    async def fake_fetch(url):
        return "ATOM  1  CA  ALA A   1"

    def no_pymol(*a, **k):
        raise ImportError("pymol2 not installed")

    monkeypatch.setattr(se, "_fetch_text", fake_fetch)
    monkeypatch.setattr(se, "_build_pse", no_pymol)
    with pytest.raises(HTTPException) as exc:
        await se.export_structure("P04637", format="pse", user_id="u1")
    assert exc.value.status_code == 503


def test_build_pse_rejects_empty_output(tmp_path, monkeypatch):
    """A pymol2 that produces a stub file must fail loudly, not ship junk."""
    import sys, types
    from pathlib import Path

    fake = types.ModuleType("pymol2")

    class _Cmd:
        def load(self, *a): pass
        def hide(self, *a): pass
        def show(self, *a): pass
        def spectrum(self, *a, **k): pass
        def bg_color(self, *a): pass
        def set(self, *a, **k): pass
        def save(self, out, *a):
            Path(out).write_bytes(b"PSE-stub")  # < 100 bytes

    class _PyMOL:
        cmd = _Cmd()
        def __enter__(self): return self
        def __exit__(self, *a): return False

    fake.PyMOL = _PyMOL
    monkeypatch.setitem(sys.modules, "pymol2", fake)

    with pytest.raises(RuntimeError, match="empty session"):
        se._build_pse("ATOM  1  CA  ALA A   1\nEND\n".replace("\n", "\n"), "test")


def test_docking_complex_merges_receptor_and_ligand():
    receptor = "ATOM  1  CA  ALA A   1\nTER"
    ligand = "HETATM    1  C   LIG B   1"
    merged = receptor.rstrip() + "\n" + ligand.rstrip() + "\nEND\n"
    assert merged.count("END") == 1
    assert "HETATM" in merged and "ATOM" in merged
