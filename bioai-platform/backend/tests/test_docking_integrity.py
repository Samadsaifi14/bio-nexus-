"""Regression checks for binary verification and invalid docking grids."""
import hashlib
from pathlib import Path

import pytest

from app.tools import docking


@pytest.fixture
def verified_binary(tmp_path, monkeypatch):
    binary = tmp_path / "vina"
    binary.write_bytes(b"verified release bytes")
    monkeypatch.setattr(docking, "_VINA_SHA256", hashlib.sha256(binary.read_bytes()).hexdigest())
    monkeypatch.setattr(docking, "_VINA_BINARY", str(binary))
    return binary


def test_cached_binary_is_checked_on_every_use(verified_binary):
    assert docking._ensure_vina() == str(verified_binary)
    verified_binary.write_bytes(b"tampered")
    with pytest.raises(RuntimeError, match="checksum mismatch"):
        docking._ensure_vina()


@pytest.mark.parametrize("digest", ["", "bad", "a" * 63])
def test_missing_or_invalid_checksum_fails_closed(verified_binary, monkeypatch, digest):
    monkeypatch.setattr(docking, "_VINA_SHA256", digest)
    with pytest.raises(RuntimeError, match="checksum is missing or invalid"):
        docking._ensure_vina()


def test_existing_download_cache_cannot_bypass_verification(tmp_path, monkeypatch):
    cache = tmp_path / "vina_bin"
    cache.mkdir()
    (cache / docking._EXE_NAME).write_bytes(b"unverified old cached binary")
    monkeypatch.setattr(docking, "_VINA_BINARY", None)
    monkeypatch.setattr(docking.tempfile, "gettempdir", lambda: str(tmp_path))
    monkeypatch.setattr(docking.os.path, "isfile", lambda p: False)
    with pytest.raises(RuntimeError, match="checksum mismatch"):
        docking._ensure_vina()


def test_bad_download_never_published(tmp_path, monkeypatch):
    monkeypatch.setattr(docking, "_VINA_BINARY", None)
    monkeypatch.setattr(docking.tempfile, "gettempdir", lambda: str(tmp_path))
    monkeypatch.setattr(docking.os.path, "isfile", lambda p: False)
    monkeypatch.setattr(docking.urllib.request, "urlretrieve", lambda url, p: Path(p).write_bytes(b"bad download"))
    with pytest.raises(RuntimeError, match="checksum mismatch"):
        docking._ensure_vina()
    assert not list((tmp_path / "vina_bin").iterdir())


@pytest.mark.parametrize("pdb", ["", "HEADER no atoms\nEND", "ATOM invalid columns",
                                   "HETATM    1  C   LIG A   1       1.000   2.000   3.000"])
def test_grid_without_receptor_coordinates_fails(pdb):
    with pytest.raises(ValueError, match="no valid finite ATOM coordinates"):
        docking.compute_grid_center(pdb)
    with pytest.raises(ValueError, match="no valid finite ATOM coordinates"):
        docking.compute_pocket_grid(pdb)


def test_nonfinite_receptor_coordinates_rejected():
    pdb = "ATOM      1  CA  ALA A   1    " + f"{float('nan'):8.3f}{2:8.3f}{3:8.3f}"
    with pytest.raises(ValueError, match="no valid finite ATOM coordinates"):
        docking.compute_grid_center(pdb)


@pytest.mark.parametrize("center,size", [(None, [20]*3), ([1, 2], [20]*3),
    ([float('nan'), 0, 0], [20]*3), ([0]*3, [20, 0, 20]),
    ([0]*3, [20, float('inf'), 20]), ([0]*3, None)])
def test_invalid_grid_rejected_before_binary_lookup(center, size, monkeypatch):
    def forbidden():
        pytest.fail("Binary lookup must not precede grid validation")
    monkeypatch.setattr(docking, "_ensure_vina", forbidden)
    with pytest.raises(ValueError):
        docking.run_vina("", "", center, size)


def test_explicit_origin_is_a_valid_center():
    assert docking._validate_grid_vector([0, 0, 0], "grid_center") == [0.0]*3

