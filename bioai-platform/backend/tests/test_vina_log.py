"""
Offline tests for AutoDock Vina 1.2.7 log parsing (Phase 3e).

The fixture log below is a literal AutoDock Vina v1.2.7 run captured from
production (docking job 5bb69899-0f1c-451c-8c01-df310ea5abf2). The parser
must decode the header, metadata, and the `mode | affinity | rmsd l.b.| rmsd u.b.`
table exactly as Vina 1.2.7 emits it.
"""

from app.tools.docking import parse_vina_log, _parse_vina_poses

import pytest

REAL_VINA_127_LOG = """AutoDock Vina v1.2.7
#################################################################
# If you used AutoDock Vina in your work, please cite:          #
#                                                               #
# J. Eberhardt, D. Santos-Martins, A. F. Tillack, and S. Forli  #
# AutoDock Vina 1.2.0: New Docking Methods, Expanded Force      #
# Field, and Python Bindings, J. Chem. Inf. Model. (2021)       #
# DOI 10.1021/acs.jcim.1c00203                                  #
#                                                               #
# O. Trott, A. J. Olson,                                        #
# AutoDock Vina: improving the speed and accuracy of docking    #
# with a new scoring function, efficient optimization and       #
# multithreading, J. Comp. Chem. (2010)                         #
# DOI 10.1002/jcc.21334                                         #
#                                                               #
# Please see https://github.com/ccsb-scripps/AutoDock-Vina for  #
# more information.                                             #
#################################################################

Scoring function : vina
Rigid receptor: /tmp/tmp31jjxdut/protein.pdbqt
Ligand: /tmp/tmp31jjxdut/ligand.pdbqt
Grid center: X 2 Y 2 Z 2
Grid size  : X 20 Y 20 Z 20
Grid space : 0.375
Exhaustiveness: 8
CPU: 0
Verbosity: 1

Computing Vina grid ... done.
Performing docking (random seed: 1431381492) ... 
0%   10   20   30   40   50   60   70   80   90   100%
|----|----|----|----|----|----|----|----|----|----|
***************************************************

mode |   affinity | dist from best mode
     | (kcal/mol) | rmsd l.b.| rmsd u.b.
-----+------------+----------+----------
   1            0          0          0
   2            0      6.008      8.028
   3            0      5.276      6.043
   4            0      5.028      6.856
   5            0      9.301      9.946
   6            0      13.25      15.24
   7    0.0008125      13.16      14.62
   8    0.0008125      8.006      8.726
   9    0.0008125      15.62      17.15
"""

# A synthetic negative-affinity log (typical real docking run) to confirm
# scientific notation + negative affinities parse correctly.
NEGATIVE_AFFINITY_LOG = """AutoDock Vina v1.2.5
Grid center: X -3.5 Y 12.75 Z 41.25
Grid size  : X 24 Y 24 Z 24
Exhaustiveness: 16
Performing docking (random seed: 123456789) ... 
mode |   affinity | dist from best mode
     | (kcal/mol) | rmsd l.b.| rmsd u.b.
-----+------------+----------+----------
   1        -8.754      0.000      0.000
   2      -8.5e+00      1.234      2.345
   3        -7.912      3.456      4.567
"""


class TestParseVinaLogReal:
    def test_version_detected(self):
        parsed = parse_vina_log(REAL_VINA_127_LOG)
        assert parsed["vina_version"] == "1.2.7"

    def test_grid_center_parsed(self):
        parsed = parse_vina_log(REAL_VINA_127_LOG)
        assert parsed["grid_center"] == [2.0, 2.0, 2.0]

    def test_grid_size_parsed(self):
        parsed = parse_vina_log(REAL_VINA_127_LOG)
        assert parsed["grid_size"] == [20.0, 20.0, 20.0]

    def test_exhaustiveness_parsed(self):
        parsed = parse_vina_log(REAL_VINA_127_LOG)
        assert parsed["exhaustiveness"] == 8

    def test_random_seed_parsed(self):
        parsed = parse_vina_log(REAL_VINA_127_LOG)
        assert parsed["random_seed"] == 1431381492

    def test_negative_random_seed(self):
        log = REAL_VINA_127_LOG.replace(
            "random seed: 1431381492", "random seed: -1704811452"
        )
        parsed = parse_vina_log(log)
        assert parsed["random_seed"] == -1704811452

    def test_scientific_notation_modes(self):
        log = REAL_VINA_127_LOG.replace(
            "   7    0.0008125      13.16      14.62",
            "   7     7.81E-06      13.16      14.62",
        )
        parsed = parse_vina_log(log)
        mode7 = next(m for m in parsed["modes"] if m["model"] == 7)
        assert mode7["affinity"] == pytest.approx(7.81e-06)

    def test_nine_modes_parsed(self):
        parsed = parse_vina_log(REAL_VINA_127_LOG)
        assert len(parsed["modes"]) == 9

    def test_mode_one_rmsd_zero(self):
        parsed = parse_vina_log(REAL_VINA_127_LOG)
        mode1 = parsed["modes"][0]
        assert mode1["model"] == 1
        assert mode1["rmsd_lb"] == 0.0
        assert mode1["rmsd_ub"] == 0.0

    def test_decimal_affinity_parsed(self):
        parsed = parse_vina_log(REAL_VINA_127_LOG)
        mode7 = next(m for m in parsed["modes"] if m["model"] == 7)
        assert mode7["affinity"] == pytest.approx(0.0008125)

    def test_mode_two_rmsd_values(self):
        parsed = parse_vina_log(REAL_VINA_127_LOG)
        mode2 = next(m for m in parsed["modes"] if m["model"] == 2)
        assert mode2["rmsd_lb"] == pytest.approx(6.008)
        assert mode2["rmsd_ub"] == pytest.approx(8.028)


class TestParseVinaLogNegative:
    def test_negative_affinity(self):
        parsed = parse_vina_log(NEGATIVE_AFFINITY_LOG)
        assert parsed["vina_version"] == "1.2.5"
        assert len(parsed["modes"]) == 3
        assert parsed["modes"][0]["affinity"] == pytest.approx(-8.754)
        assert parsed["modes"][0]["rmsd_lb"] == 0.0
        assert parsed["modes"][0]["rmsd_ub"] == 0.0

    def test_scientific_notation(self):
        parsed = parse_vina_log(NEGATIVE_AFFINITY_LOG)
        assert parsed["modes"][1]["affinity"] == pytest.approx(-8.5)

    def test_negative_grid_center(self):
        parsed = parse_vina_log(NEGATIVE_AFFINITY_LOG)
        assert parsed["grid_center"] == [-3.5, 12.75, 41.25]

    def test_random_seed(self):
        parsed = parse_vina_log(NEGATIVE_AFFINITY_LOG)
        assert parsed["random_seed"] == 123456789

    def test_exhaustiveness(self):
        parsed = parse_vina_log(NEGATIVE_AFFINITY_LOG)
        assert parsed["exhaustiveness"] == 16


class TestParseVinaEmpty:
    def test_empty_log(self):
        parsed = parse_vina_log("")
        assert parsed["vina_version"] == ""
        assert parsed["modes"] == []
        assert parsed["random_seed"] is None

    def test_no_table_log(self):
        parsed = parse_vina_log("AutoDock Vina v1.2.7\nScoring function : vina\n")
        assert parsed["vina_version"] == "1.2.7"
        assert parsed["modes"] == []


class TestParseVinaPoses:
    def test_poses_carry_rmsd(self):
        output_pdbqt = (
            "MODEL 1\n"
            "HETATM    1  C   LIG A 1       1.000   2.000   3.000  1.00  0.00\n"
            "ENDMDL\n"
            "MODEL 2\n"
            "HETATM    1  C   LIG A 1       2.000   3.000   4.000  1.00  0.00\n"
            "HETATM    2  N   LIG A 1       2.500   3.500   4.500  1.00  0.00\n"
            "ENDMDL\n"
            "END\n"
        )
        poses = _parse_vina_poses(output_pdbqt, REAL_VINA_127_LOG)
        by_model = {p["model"]: p for p in poses}
        assert by_model[1]["rmsd_lb"] == 0.0
        assert by_model[1]["rmsd_ub"] == 0.0
        assert by_model[2]["rmsd_lb"] == pytest.approx(6.008)
        assert by_model[2]["rmsd_ub"] == pytest.approx(8.028)
        assert by_model[1]["atoms"] == 1
        assert by_model[2]["atoms"] == 2
        assert by_model[2]["affinity"] == 0.0

    def test_poses_missing_mode_has_null_rmsd(self):
        output_pdbqt = (
            "MODEL 42\n"
            "HETATM    1  C   LIG A 1       1.000   2.000   3.000  1.00  0.00\n"
            "ENDMDL\n"
            "END\n"
        )
        poses = _parse_vina_poses(output_pdbqt, REAL_VINA_127_LOG)
        assert len(poses) == 1
        assert poses[0]["rmsd_lb"] is None
        assert poses[0]["rmsd_ub"] is None
        assert poses[0]["affinity"] is None
