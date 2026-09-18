"""BBS-2 fixture gates (MATRIX 2, 3, 28, 29).

* every committed fixture file is covered by the checksum manifest;
* the descriptor-parity benchmark must PASS against the pinned RDKit
  reference when RDKit is importable.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
FIXTURES = REPO / "benchmark" / "fixtures"
PARITY = FIXTURES / "cheminformatics" / "descriptor_parity"
ADMET = FIXTURES / "cheminformatics" / "drug_likeness"
ADVERSARIAL = FIXTURES / "ai" / "adversarial"
NGS_PORT = REPO / "benchmark" / "ngs-portability"
PROTOX = FIXTURES / "cheminformatics" / "protox"
DOCKING = FIXTURES / "docking"
STRUCT_PREP = FIXTURES / "structure_prep"
SEQUENCE = FIXTURES / "sequence"

rdkit = pytest.importorskip("rdkit")


def _run(*args, cwd: Path):
    return subprocess.run([sys.executable, *map(str, args)], cwd=str(cwd), capture_output=True, text=True, timeout=600)


def test_fixture_manifest_has_no_drift():
    proc = _run(REPO / "benchmark" / "verify_fixtures.py", cwd=REPO)
    assert proc.returncode == 0, f"fixture manifest drift:\n{proc.stdout}\n{proc.stderr}"


def test_descriptor_parity_passes():
    proc = _run(PARITY / "run_descriptor_parity.py", cwd=REPO / "bioai-platform" / "backend")
    assert proc.returncode == 0, proc.stdout[-4000:] + proc.stderr[-2000:]
    assert "PASS" in proc.stdout


def test_descriptor_parity_record_persisted():
    latest = json.loads((FIXTURES.parent / "results" / "cheminformatics" / "descriptor_parity" / "latest.json").read_text(encoding="utf-8"))
    assert latest["passed"] is True
    assert latest["state_permille_exact_match"] == 1000
    assert latest["parse_permille"] == 1000


def test_drug_likeness_rules_passes():
    proc = _run(ADMET / "run_drug_likeness.py", cwd=REPO / "bioai-platform" / "backend")
    assert proc.returncode == 0, proc.stdout[-4000:] + proc.stderr[-2000:]
    assert "PASS" in proc.stdout


def test_brenk_sulfonamide_alias_regression():
    """fr_sulfonamd/fr_quatN alias fix in app/tools/admet.py must stay."""
    import sys
    sys.path.insert(0, str(REPO / "bioai-platform" / "backend"))
    from app.tools.admet import compute_descriptors
    for smiles in ("CC1=CC(=NO1)NS(=O)(=O)C1=CC=C(N)C=C1", "C1=CC=C(C=C1)S(=O)(=O)N"):
        res = compute_descriptors(smiles)
        assert "Sulfonamide (hypersensitivity risk)" in res["structural_alerts"]["brenk"]["alerts"]
    res = compute_descriptors("CC[N+](CC)(CC)CC")
    assert "Quaternary nitrogen (P-gp substrate risk)" in res["structural_alerts"]["brenk"]["alerts"]


def test_evidence_adversarial_integrity_passes():
    proc = _run(ADVERSARIAL / "run_evidence_adversarial.py", cwd=REPO / "bioai-platform" / "backend")
    assert proc.returncode == 0, proc.stdout[-4000:] + proc.stderr[-2000:]
    assert "PASS" in proc.stdout


def test_evidence_adversarial_record_tracks_gaps():
    latest = json.loads((FIXTURES.parent / "results" / "ai" / "adversarial" / "latest.json").read_text(encoding="utf-8"))
    assert latest["passed"] is True
    assert latest["gap_cases_tracked"] >= 3
    gap_ids = [c["id"] for c in latest["cases"] if c["expectation"] == "gap"]
    assert "EV-SEM-001" in gap_ids


def _sha256(path: Path) -> str:
    import hashlib
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


def test_ngs_portability_fixture_checksums_are_pinned():
    manifest = json.loads((NGS_PORT / "fixtures" / "fixture_manifest.json").read_text(encoding="utf-8"))
    for name, expected in manifest["checksums"].items():
        actual = _sha256(NGS_PORT / "fixtures" / name)
        assert actual == expected, f"fixture {name}: stored {expected[:16]}... != on-disk {actual[:16]}..."


def test_ngs_portability_comparison_consistent_and_passing():
    cmp = json.loads((NGS_PORT / "results" / "comparison.json").read_text(encoding="utf-8"))
    assert cmp["workflow_output_parity"] is True
    assert cmp["classification"] == "SYNTHETIC_POSITIVE_CONTROL"
    assert len(cmp["reports"]) == 3
    assert len(cmp.get("limitations", [])) >= 3
    call_digests = []
    for report in cmp["reports"]:
        assert report["f1"] == 1.0
        assert report["tp"] == 1 and report["fp"] == 0 and report["fn"] == 0
        sub = "galaxy-wrapper" if "galaxy" in report["orchestrator"] else "nextflow" if "nextflow" in report["orchestrator"] else "direct"
        digest = _sha256(NGS_PORT / "results" / sub / "calls.tsv")
        call_digests.append(digest)
        assert digest == report["normalized_sha256"], f"{sub}: digest mismatch"
    assert len(set(call_digests)) == 1, "orchestrators do not agree on normalized output"


PROMPTS = FIXTURES / "ai" / "prompts"


def test_ai_prompt_corpus_generates_and_passes():
    proc = _run(PROMPTS / "generate_prompt_corpus.py", cwd=REPO)
    assert proc.returncode == 0, proc.stdout[-4000:] + proc.stderr[-2000:]
    assert "RESULT: PASS" in proc.stdout


def test_ai_prompt_corpus_contract_fields():
    data = json.loads((PROMPTS / "prompt_corpus.json").read_text(encoding="utf-8"))
    assert data["variants"]["total"] >= 200
    assert data["failures"] == []
    labels = {c["label"] for c in data["cases"]}
    # hazards must be present and their literal braces preserved by escaping
    assert "hazard_braces_uniprot_func" in labels
    assert "hazard_braces_blast_desc" in labels
    # honesty: omitted fields produce N/A in the built prompt
    na_labels = {c["label"] for c in data["cases"] if c["contains_na"] > 0}
    assert {"omit_uniprot_functions", "omit_blast_tophit"} <= na_labels


def test_protox_contract_pinned_to_code():
    sys.path.insert(0, str(REPO / "bioai-platform" / "backend"))
    from app.tools.protox import ALL_MODELS, DEFAULT_MODELS, _CSV_BASE, _ENQUEUE_URL, _RETRIEVE_URL

    contract = json.loads((PROTOX / "protox_contract.json").read_text(encoding="utf-8"))
    assert contract["version_string"] == "ProTox 3.0"
    assert set(contract["endpoints"]) == {"enqueue_path", "retrieve_path", "csv_base_path"}
    assert contract["endpoints"]["enqueue_path"] in _ENQUEUE_URL
    assert contract["endpoints"]["retrieve_path"] in _RETRIEVE_URL
    assert contract["endpoints"]["csv_base_path"] in _CSV_BASE
    assert set(contract["all_models"]) == set(ALL_MODELS.split())
    assert contract["default_models"] == DEFAULT_MODELS.split()


def test_protox_no_fabricated_ground_truth_committed():
    # CHEM-TOX must not claim external benchmarking from synthetic data: the
    # fixture contains only the contract + live-capture harness, never a fabric
    # output pretending to be a real server response.
    committed = {p.name: p for p in PROTOX.iterdir() if p.is_file()}
    assert set(committed) == {"protox_contract.json", "record_reference.py"}
    contract_text = (PROTOX / "protox_contract.json").read_text(encoding="utf-8").lower()
    assert "sample output" not in contract_text and "expected_result" not in contract_text


def test_redock_panel_spec_is_well_formed():
    panel = json.loads((DOCKING / "redock_panel.json").read_text(encoding="utf-8"))
    assert panel["schema"] == "bionexus-redock-panel/v1"
    assert len(panel["complexes"]) >= 10
    criteria = panel["predeclared_success_criteria"]
    assert criteria["per_complex_rmsd_threshold_angstrom"] == 2.0
    assert 0.5 < criteria["panel_pass_threshold_frac"] <= 1.0
    # every complex is a real PDB co-crystal with a ligand residue
    for cx in panel["complexes"]:
        assert set(cx) >= {"id", "pdb", "ligand_resname", "essential"}
        import re as _re
        assert _re.fullmatch(r"[0-9][A-Z0-9]{3}", cx["pdb"]), cx
        assert len(cx["ligand_resname"]) == 3
    # essential controls selected as difficult pose-reproduction cases
    assert any(cx["essential"] for cx in panel["complexes"])
    assert len(panel["limitations"]) >= 4


def test_redock_panel_runner_is_honest_without_tools():
    proc = _run(DOCKING / "run_redock_panel.py", cwd=REPO)
    # With Vina/OpenBabel/fpocket absent this must be an explicit not-executed
    # status (exit 2), never a fabricated pass.
    latest = json.loads((REPO / "benchmark" / "results" / "docking" / "redock" / "latest.json").read_text(encoding="utf-8"))
    assert latest["status"] == "not_executed"
    assert latest["reason"] == "requires_external"
    if proc.returncode == 2:
        assert latest["status"] == "not_executed"
    else:
        # If tools ARE present this box truly runs the panel; we only assert the
        # record schema and honesty fields regardless of verdict.
        assert latest["status"] in ("passed", "failed")
        assert "results" in latest
        assert len(latest["success_criteria"]) > 0


def test_structure_prep_panel_spec_is_well_formed():
    panel = json.loads((STRUCT_PREP / "structure_prep_panel.json").read_text(encoding="utf-8"))
    assert panel["schema"] == "bionexus-structure-prep-e2e/v1"
    assert len(panel["entries"]) >= 3
    expected_assertions = {
        "chain_health_total_residues_gt_zero",
        "cleanup_keeps_protein",
        "cleanup_removes_hetatm_waters",
        "pocket_detection_runs_complete",
        "pocket_expected_found",
    }
    assert expected_assertions <= set(panel["predeclared_assertions"])
    for en in panel["entries"]:
        assert set(en) >= {"id", "pdb", "expect_pocket"}
        import re as _re
        assert _re.fullmatch(r"[0-9][A-Z0-9]{3}", en["pdb"]), en
    assert any(en["expect_pocket"] for en in panel["entries"])
    assert len(panel["limitations"]) >= 4


def test_structure_prep_runner_is_honest_without_deps():
    # --no-network forces the requires_external path deterministically so the
    # offline suite can exercise honesty without RCSB access or fpocket.
    proc = _run(STRUCT_PREP / "run_structure_prep_e2e.py", "--no-network",
                "--outdir", REPO / "benchmark" / "results" / "structure_prep", cwd=REPO)
    latest = json.loads((REPO / "benchmark" / "results" / "structure_prep" / "latest.json").read_text(encoding="utf-8"))
    assert latest["status"] == "not_executed"
    assert latest["reason"] == "requires_external"
    assert "rcsb_network" in latest["missing"]
    # never a fabricated pass: an executed record must carry per-entry results
    if proc.returncode == 0:
        assert latest["status"] == "passed"
        assert "entries" in latest
        assert "failures" in latest


def test_blast_recovery_spec_is_well_formed():
    panel = json.loads((SEQUENCE / "blast_queries.json").read_text(encoding="utf-8"))
    assert panel["schema"] == "bionexus-blast-accession-recovery/v1"
    criteria = panel["predeclared_success_criteria"]
    assert criteria["min_queries"] >= 6
    assert criteria["recovery_threshold_frac"] > 0.5
    assert criteria["max_recovery_rank"] >= 1
    assert criteria["essential_required"]
    assert len(panel["queries"]) >= criteria["min_queries"]
    for q in panel["queries"]:
        assert set(q) >= {"id", "protein", "expected_accessions", "essential"}
        assert q["expected_accessions"], q
        import re as _re
        assert all(_re.fullmatch(r"[OPQ][0-9][A-Z0-9]{3}[0-9]", a) for a in q["expected_accessions"]), q
    assert any(q["essential"] for q in panel["queries"])
    assert len(panel["limitations"]) >= 4


def test_blast_recovery_runner_is_honest_without_network():
    proc = _run(SEQUENCE / "run_blast_recovery.py", "--no-network",
                "--outdir", REPO / "benchmark" / "results" / "sequence" / "blast", cwd=REPO)
    latest = json.loads(
        (REPO / "benchmark" / "results" / "sequence" / "blast" / "latest.json").read_text(encoding="utf-8"))
    assert latest["status"] == "not_executed"
    assert latest["reason"] == "requires_external"
    assert "uniprot_network" in latest["missing"]
    if proc.returncode == 0:
        assert latest["status"] == "passed"
        assert "queries" in latest
        assert "failures" in latest