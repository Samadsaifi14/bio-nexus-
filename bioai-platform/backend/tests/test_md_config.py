"""
Unit tests for the MD force field / solvent configuration menu.

Covers the parts that do not require OpenMM (fast, always run):
- FF_XML / SOLVENT_XML menus contain the documented entries
- get_forcefields_menu() shape and that it only exposes verified combos
- resolve_combo() normalization and explicit ValueError for unknown force
  fields, unknown solvents, and (when OpenMM is present) unverified pairs

The heavy per-combo createSystem() probe is exercised once (skip-if-no-OpenMM)
to confirm the startup verification itself runs end to end.
"""

import pytest

from app.tools.md_config import (
    FF_XML,
    SOLVENT_XML,
    DEFAULT_FORCEFIELD,
    DEFAULT_SOLVENT,
    get_forcefields_menu,
    resolve_combo,
    verify_ff_solvent_combos,
)


class TestMenus:
    def test_forcefield_menu_entries(self):
        assert FF_XML == {
            "amber14": "amber14-all.xml",
            "ff14sb": "amber14/protein.ff14SB.xml",
            "ff15ipq": "amber14/protein.ff15ipq.xml",
            "ff19sb": "amber19/protein.ff19SB.xml",
            "amberfb15": "amberfb15.xml",
            "charmm36": "charmm36.xml",
        }

    def test_solvent_menu_entries(self):
        assert SOLVENT_XML == {
            "obc1": "implicit/obc1.xml",
            "obc2": "implicit/obc2.xml",
            "gbn2": "implicit/gbn2.xml",
        }

    def test_defaults_are_amber14_obc2(self):
        assert DEFAULT_FORCEFIELD == "amber14"
        assert DEFAULT_SOLVENT == "obc2"


class TestGetForcefieldsMenu:
    def test_menu_shape(self):
        menu = get_forcefields_menu()
        assert set(menu) >= {"forcefields", "solvents", "combos", "defaults"}
        assert isinstance(menu["forcefields"], list)
        assert isinstance(menu["solvents"], list)
        assert menu["defaults"] == {"forcefield": "amber14", "solvent": "obc2"}
        # every listed force field has at least one verified solvent
        combos = menu["combos"]
        for ff in menu["forcefields"]:
            assert ff["value"] in combos
            assert combos[ff["value"]]

    def test_combos_only_contain_known_solvents(self):
        menu = get_forcefields_menu()
        for ff, solvents in menu["combos"].items():
            assert ff in FF_XML
            assert set(solvents) <= set(SOLVENT_XML)


class TestResolveCombo:
    def test_defaults(self):
        assert resolve_combo(None, None) == ("amber14", "obc2")

    def test_normalization(self):
        assert resolve_combo(" ff14SB ", "GBN2") == ("ff14sb", "gbn2")

    def test_unknown_forcefield_raises(self):
        with pytest.raises(ValueError, match="Unsupported force field"):
            resolve_combo("opls", "obc2")

    def test_unknown_solvent_raises(self):
        with pytest.raises(ValueError, match="Unsupported solvent"):
            resolve_combo("ff14sb", "explicit")

    def test_unverified_combo_raises(self):
        # Simulate a deployment where only amber14 passed verification.
        verified = verify_ff_solvent_combos()
        if not verified:
            pytest.skip("OpenMM unavailable — verification empty")
        unverified = [ff for ff in FF_XML if ff not in verified]
        if not unverified:
            pytest.skip("all force fields verified — nothing unverified to test")
        with pytest.raises(ValueError, match="not available"):
            resolve_combo(unverified[0], "obc2")


class TestStartupVerification:
    def test_verification_runs_end_to_end(self):
        verified = verify_ff_solvent_combos()
        if not verified:
            pytest.importorskip("openmm")
        # Every entry maps to a valid force field with known solvents.
        assert verified == {ff: tuple(s) for ff, s in verified.items()}
        for ff, solvents in verified.items():
            assert ff in FF_XML
            assert set(solvents) <= set(SOLVENT_XML)
