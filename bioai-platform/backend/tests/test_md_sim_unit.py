"""
Unit tests for the MD simulation engine (no network; OpenMM only for the
thermostat test, which auto-skips when OpenMM is absent).

Covers:
- Kabsch RMSD correctness (rigid-body invariance, known displacements)
- Adaptive production length scaling (size-dependent, bounded)
- Radius of gyration (translation invariance, scaling, known geometry)
- Shrake–Ruger SASA (single atom, buried area, random-cloud bounds, rotation)
- Langevin thermostat reaches its target temperature (random data)
- Position conversion
- JSON-safe native conversion
"""

import numpy as np
import pytest

from app.tools.md_sim import (
    _kabsch_rmsd,
    _adaptive_production_steps,
    _positions_to_np,
    _radius_of_gyration,
    _sasa_shrake_ruger,
    _temperature_from_ke,
    _to_native,
    _PROBE_RADIUS_ANGSTROM,
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

        # OpenMM positions are in nanometers; conversion must scale to Å (×10).
        positions = [P(1, 2, 3), P(4, 5, 6)]
        out = _positions_to_np(positions)
        assert out.shape == (2, 3)
        np.testing.assert_allclose(out[0], [10, 20, 30])
        np.testing.assert_allclose(out[1], [40, 50, 60])


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


class TestRadiusOfGyration:
    def test_empty_input_zero(self):
        assert _radius_of_gyration(np.zeros((0, 3))) == 0.0

    def test_single_atom_zero(self):
        assert _radius_of_gyration(np.array([[1.0, 2.0, 3.0]])) == 0.0

    def test_known_geometry_cube_vertices(self):
        # Cube vertices at (±1, ±1, ±1): centroid at origin, every atom at distance √3.
        coords = np.array([[-1, -1, -1], [1, -1, -1], [-1, 1, -1], [-1, -1, 1],
                           [1, 1, 1], [-1, 1, 1], [1, -1, 1], [1, 1, -1]], dtype=float)
        assert abs(_radius_of_gyration(coords) - np.sqrt(3)) < 1e-9

    def test_translation_invariance(self):
        rng = np.random.default_rng(2)
        coords = rng.normal(size=(60, 3)) * 8
        shifted = coords + np.array([7.0, -4.0, 3.0])
        assert abs(_radius_of_gyration(coords) - _radius_of_gyration(shifted)) < 1e-9

    def test_scaling(self):
        rng = np.random.default_rng(5)
        coords = rng.normal(size=(40, 3)) * 5
        assert abs(_radius_of_gyration(2 * coords) - 2 * _radius_of_gyration(coords)) < 1e-9

    def test_matches_manual_formula(self):
        rng = np.random.default_rng(9)
        coords = rng.normal(size=(50, 3)) * 10
        com = coords.mean(axis=0)
        expected = float(np.sqrt(((coords - com) ** 2).sum(axis=1).mean()))
        assert abs(_radius_of_gyration(coords) - expected) < 1e-9


class TestSASA:
    def test_empty_input_zero(self):
        assert _sasa_shrake_ruger(np.zeros((0, 3)), np.zeros((0,))) == 0.0

    def test_single_atom_full_sphere(self):
        r = 1.7
        sasa = _sasa_shrake_ruger(np.array([[0.0, 0.0, 0.0]]), np.array([r]))
        expected = 4 * np.pi * (r + _PROBE_RADIUS_ANGSTROM) ** 2
        assert abs(sasa - expected) < expected * 0.02

    def test_overlap_buries_surface(self):
        # Two atoms 1 Å apart overlap heavily: surface must be between one and
        # two full spheres.
        r = 1.7
        coords = np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0]])
        radii = np.array([r, r])
        sasa = _sasa_shrake_ruger(coords, radii)
        single = 4 * np.pi * (r + _PROBE_RADIUS_ANGSTROM) ** 2
        assert single < sasa < 2 * single

    def test_separated_atoms_sum_to_twice_single(self):
        r = 1.7
        d = 2 * (r + _PROBE_RADIUS_ANGSTROM) + 1.0  # well beyond interaction range
        coords = np.array([[0.0, 0.0, 0.0], [d, 0.0, 0.0]])
        radii = np.array([r, r])
        sasa = _sasa_shrake_ruger(coords, radii)
        single = 4 * np.pi * (r + _PROBE_RADIUS_ANGSTROM) ** 2
        assert abs(sasa - 2 * single) < single * 0.05

    def test_random_cloud_bounded(self):
        rng = np.random.default_rng(11)
        coords = rng.normal(size=(300, 3)) * 12
        radii = rng.choice([1.7, 1.55, 1.52, 1.2], size=300)
        sasa = _sasa_shrake_ruger(coords, radii)
        assert sasa > 0
        sphere_sum = 4 * np.pi * ((radii + _PROBE_RADIUS_ANGSTROM) ** 2).sum()
        assert sasa < sphere_sum

    def test_rotation_invariance(self):
        rng = np.random.default_rng(13)
        coords = rng.normal(size=(200, 3)) * 10
        radii = rng.choice([1.7, 1.55, 1.52, 1.8, 1.2], size=200)
        R = _rotz(0.7) @ _roty(1.2)
        s1 = _sasa_shrake_ruger(coords, radii)
        s2 = _sasa_shrake_ruger(coords @ R.T, radii)
        assert abs(s1 - s2) / s1 < 0.02

    def test_translation_invariance(self):
        rng = np.random.default_rng(17)
        coords = rng.normal(size=(150, 3)) * 9
        radii = rng.choice([1.7, 1.55, 1.52], size=150)
        s1 = _sasa_shrake_ruger(coords, radii)
        s2 = _sasa_shrake_ruger(coords + np.array([4.0, -6.0, 2.0]), radii)
        assert abs(s1 - s2) / s1 < 0.02


class TestTemperatureFromKE:
    def test_zero_dof_returns_zero(self):
        assert _temperature_from_ke(10.0, 0) == 0.0
        assert _temperature_from_ke(10.0, -3) == 0.0

    def test_known_value(self):
        # T = 2·KE / (k_B·N_dof); solve for KE to give exactly 300 K.
        n_dof = 597
        ke = 0.5 * 0.0083144621 * 300 * n_dof
        assert abs(_temperature_from_ke(ke, n_dof) - 300.0) < 1e-9

    def test_scales_linearly_with_ke(self):
        t1 = _temperature_from_ke(10.0, 100)
        t2 = _temperature_from_ke(20.0, 100)
        assert abs(t2 - 2 * t1) < 1e-9


class TestLangevinTemperature:
    def test_random_system_reaches_thermostat_target(self):
        openmm = pytest.importorskip("openmm")
        from openmm import unit

        rng = np.random.default_rng(42)
        n_particles = 200

        # Force-free system: only the Langevin thermostat acts, so the kinetic
        # energy must converge to the Maxwell–Boltzmann average at 300 K.
        # (Adding LJ forces would make random overlapping atoms explode — a
        # physical, not numerical, effect — so we keep the test force-free.)
        system = openmm.System()
        for _ in range(n_particles):
            system.addParticle(12.0 * unit.dalton)

        integrator = openmm.LangevinMiddleIntegrator(
            300 * unit.kelvin, 1 / unit.picosecond, 2 * unit.femtoseconds)
        context = openmm.Context(system, integrator, openmm.Platform.getPlatformByName("CPU"))
        try:
            context.setPositions(rng.normal(size=(n_particles, 3)) * unit.nanometer)
            integrator.step(2000)  # warm-up from zero velocities
            temps = []
            for _ in range(50):
                integrator.step(20)
                st = context.getState(getEnergy=True)
                ke = st.getKineticEnergy().value_in_unit(unit.kilojoule_per_mole)
                temps.append(_temperature_from_ke(ke, 3 * n_particles - 3))
            mean_temp = float(np.mean(temps))
            assert 250 < mean_temp < 350, f"mean temperature {mean_temp:.1f} K far from 300 K target"
        finally:
            del context
