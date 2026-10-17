import numpy as np

from app.md.advanced_analysis import analyze_trajectory, align_trajectory, dccm, pca


def _rigid_body_frames():
    base=np.array([[0.,0.,0.],[1.,0.,0.],[0.,1.,0.],[0.,0.,1.]])
    theta=np.deg2rad(35)
    rot=np.array([[np.cos(theta),-np.sin(theta),0],[np.sin(theta),np.cos(theta),0],[0,0,1.]])
    moved=base@rot.T+np.array([10.,-4.,3.])
    return np.stack([base,moved])


def test_kabsch_removes_rigid_translation_and_rotation():
    result=analyze_trajectory(_rigid_body_frames().tolist(),pca_components=2)
    assert max(result["rmsd"]["series"]) < 1e-10
    assert result["alignment"]["method"]=="Kabsch"


def test_missing_topology_metrics_are_not_fabricated():
    result=analyze_trajectory(_rigid_body_frames().tolist())
    assert result["sasa"]["available"] is False
    assert result["hydrogen_bonds"]["available"] is False
    assert result["secondary_structure_timeline"]["available"] is False


def test_contact_dccm_and_pca_have_expected_dimensions():
    frames=_rigid_body_frames()
    aligned=align_trajectory(frames)
    d=dccm(aligned)
    assert len(d["matrix"])==4
    assert all(len(row)==4 for row in d["matrix"])
    p=pca(aligned,2)
    assert p["components"]==2
    assert len(p["scores"])==2


def test_sasa_is_available_only_with_radii():
    frames=_rigid_body_frames().tolist()
    result=analyze_trajectory(frames,atom_radii=[1.7,1.7,1.7,1.7])
    assert result["sasa"]["method"]=="Shrake-Rupley"
    assert len(result["sasa"]["series"])==2
    assert all(v>0 for v in result["sasa"]["series"])


def test_free_energy_reports_limitation_for_insufficient_pca_dimensions():
    one_atom=[[[0.,0.,0.]],[[0.1,0.,0.]],[[0.2,0.,0.]]]
    result=analyze_trajectory(one_atom,pca_components=1)
    assert result["free_energy_landscape"]["available"] is False


def test_seeded_rigid_rotations_preserve_coordinates_and_distances():
    rng = np.random.default_rng(1701)
    reference = rng.normal(size=(12, 3))
    for _ in range(10):
        rotation, _ = np.linalg.qr(rng.normal(size=(3, 3)))
        if np.linalg.det(rotation) < 0:
            rotation[:, 0] *= -1
        moved = reference @ rotation + rng.normal(size=3) * 10
        aligned = align_trajectory(np.stack([reference, moved]))
        np.testing.assert_allclose(aligned[1], reference, atol=1e-12)
        before = np.linalg.norm(moved[:, None] - moved[None, :], axis=-1)
        after = np.linalg.norm(aligned[1, :, None] - aligned[1, None, :], axis=-1)
        np.testing.assert_allclose(after, before, atol=1e-12)


def test_alignment_does_not_reflect_a_chiral_structure():
    reference = _rigid_body_frames()[0]
    mirror = reference * np.array([-1., 1., 1.])
    aligned = align_trajectory(np.stack([reference, mirror]))
    assert np.sqrt(np.mean(np.sum((aligned[1] - reference) ** 2, axis=1))) > 0.1
