"""
Unit tests for the MD simulation engine (no network, no OpenMM needed).

Covers:
- Kabsch RMSD correctness (rigid-body invariance, known displacements)
- Adaptive production length scaling (size-dependent, bounded)
- Position conversion
- JSON-safe native conversion
"""

import numpy as np
import pytest

from app.tools.md_sim import (
    _kabsch_rmsd,
    _adaptive_production_steps,
    _positions_to_np,
    _to_native,
)


def _rotz(a):
    c, s = np.cos(a), np.sin(a)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])


def _roty(a):
    c, s = np.cos(a), np.sin(a)
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])


class TestKabschRMSD:
    def test_identical_coordinates(self):
        ref = np.random.RandomState(0).rand(100, 3) * 10
        assert _kabsch_rmsd(ref, ref.copy()) < 1e-9

    def test_rigid_body_invariance(self):
        """Rotation + translation must yield RMSD ~0 (Kabsch removes both)."""
        rng = np.random.RandomState(1)
        ref = rng.rand(80, 3) * 15
        R = _rotz(0.7) @ _roty(1.2) @ _rotz(0.3)
        mov = ref @ R.T + np.array([5.0, -3.0, 2.0])
        assert _kabsch_rmsd(ref, mov) < 1e-8

    def test_pure_translation_invariance(self):
        """A uniform translation alone must yield RMSD ~0."""
        rng = np.random.RandomState(7)
        ref = rng.rand(60, 3) * 10
        mov = ref + np.array([1.0, 2.0, -3.0])
        assert _kabsch_rmsd(ref, mov) < 1e-8

    def test_noise_upper_bound(self):
        """Adding noise must produce RMSD <= per-atom raw (un-aligned) RMSD, and > 0."""
        rng = np.random.RandomState(4)
        ref = rng.rand(100, 3) * 10
        noise = rng.normal(0, 0.5, ref.shape)
        mov = ref + noise
        # per-atom RMSD of un-aligned pair = sqrt(mean over ALL coords of noise^2) * sqrt(3)
        raw = float(np.sqrt((noise**2).mean())) * np.sqrt(3)
        got = _kabsch_rmsd(ref, mov)
        assert 0.0 < got <= raw * 1.001
        assert got > raw * 0.7  # optimal rotation shouldn't over-correct

    def test_single_atom(self):
        # A single atom always centers to the origin, so RMSD is 0.
        assert _kabsch_rmsd(np.array([[0.0, 0, 0]]), np.array([[1.0, 0, 0]])) < 1e-9

    def test_shape_mismatch_raises(self):
        with pytest.raises(ValueError):
            _kabsch_rmsd(np.zeros((3, 3)), np.zeros((4, 3)))

    def test_empty_input_returns_zero(self):
        assert _kabsch_rmsd(np.zeros((0, 3)), np.zeros((0, 3))) == 0.0


class TestAdaptiveProductionSteps:
    def test_small_protein_gets_target(self):
        assert _adaptive_production_steps(642) >= 100_000

    def test_larger_protein_gets_fewer_steps(self):
        steps_big = _adaptive_production_steps(30_000)
        steps_huge = _adaptive_production_steps(60_000)
        assert steps_big > steps_huge

    def test_never_exceeds_cap(self):
        assert _adaptive_production_steps(10) <= 1000 * 500  # 1 ns cap

    def test_never_below_floor(self):
        assert _adaptive_production_steps(1_000_000) >= 2 * 500

    def test_zero_atoms_returns_target(self):
        assert _adaptive_production_steps(0) == 250 * 500


class TestPositionConversion:
    def test_converts_openmm_like_positions(self):
        class P:
            def __init__(self, x, y, z):
                self.x, self.y, self.z = x, y, z

        positions = [P(1, 2, 3), P(4, 5, 6)]
        out = _positions_to_np(positions)
        assert out.shape == (2, 3)
        np.testing.assert_allclose(out[0], [1, 2, 3])
        np.testing.assert_allclose(out[1], [4, 5, 6])


class TestToNative:
    def test_converts_numpy_types(self):
        out = _to_native({"a": np.float32(1.5), "b": np.int64(3), "c": np.array([1.0, 2.0])})
        assert isinstance(out["a"], float)
        assert isinstance(out["b"], int)
        assert isinstance(out["c"], list)

    def test_nested_structures(self):
        out = _to_native([{"x": np.float64(1.0)}, [np.int32(2)]])
        assert isinstance(out[0]["x"], float)
        assert isinstance(out[1][0], int)
