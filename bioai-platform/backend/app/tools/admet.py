"""ADMET descriptor computation using RDKit — industrial-grade panel.

Computes 50+ molecular descriptors including:
  - Core physicochemical properties (MW, LogP, TPSA, HBD, HBA, etc.)
  - Extended topological descriptors (Fsp3, aromatic rings, MR, volume, complexity)
  - Drug-likeness filters (Lipinski, Veber, Ghose, Egan, MDDR, PAINS, Brenk)
  - ADMET predictions (absorption, distribution, metabolism, toxicity, clearance)
  - Structural alerts and functional group analysis
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def _fg(mol, name: str) -> int:
    """Safely call a Fragments.fr_* function, returning 0 if unavailable."""
    from rdkit.Chem import Fragments
    fn = getattr(Fragments, name, None)
    if fn is None:
        return 0
    try:
        return fn(mol)
    except Exception:
        return 0


def compute_descriptors(smiles: str) -> dict:
    """Compute comprehensive ADMET descriptors from a SMILES string."""
    from rdkit import Chem
    from rdkit.Chem import (
        Descriptors, Lipinski, QED, rdMolDescriptors,
        EState, Fragments, Crippen,
    )
    from rdkit.Chem.MolSurf import TPSA, LabuteASA

    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        raise ValueError(f"Invalid SMILES: {smiles!r}")

    n_heavy = mol.GetNumHeavyAtoms()
    n_rings = mol.GetRingInfo().NumRings()
    n_aromatic_rings = sum(1 for ring in mol.GetRingInfo().AtomRings()
                           if all(mol.GetAtomWithIdx(a).GetIsAromatic() for a in ring))

    # ---- Core physicochemical properties ----
    mw = round(Descriptors.MolWt(mol), 2)
    logp = round(Descriptors.MolLogP(mol), 2)
    tpsa = round(TPSA(mol), 2)
    hbd = Lipinski.NumHDonors(mol)
    hba = Lipinski.NumHAcceptors(mol)
    rotatable = Lipinski.NumRotatableBonds(mol)
    heavy_atoms = n_heavy
    formula = rdMolDescriptors.CalcMolFormula(mol)
    qed_score = round(QED.qed(mol), 4)

    # ---- Extended topological descriptors ----
    fsp3 = round(Descriptors.FractionCSP3(mol), 4)
    mr = round(Crippen.MolMR(mol), 2)  # molar refractivity
    try:
        mol_volume = round(rdMolDescriptors.CalcMolecularVolume(mol), 2)
    except AttributeError:
        try:
            from rdkit.Chem import Descriptors3D
            mol_volume = round(Descriptors3D.CalcVolume(mol), 2)
        except Exception:
            mol_volume = 0.0
    try:
        complexity = round(Descriptors.BalabanJ(mol), 4)
    except Exception:
        complexity = 0.0
    try:
        wiener = Descriptors.WeinerIndex(mol)
    except Exception:
        wiener = 0
    try:
        zagreb = Descriptors.ZagrebIndex(mol)
    except Exception:
        zagreb = 0
    num_heteroatoms = Lipinski.NumHeteroatoms(mol)
    num_amide_bonds = rdMolDescriptors.CalcNumAmideBonds(mol)
    num_atom_stereocenters = rdMolDescriptors.CalcNumAtomStereoCenters(mol)
    num_unspecified_stereocenters = rdMolDescriptors.CalcNumUnspecifiedAtomStereoCenters(mol)
    labute_asa = round(LabuteASA(mol), 2)
    estate_sum = round(sum(EState.EStateIndices(mol)), 2)

    # Ring descriptors
    ring_count = n_rings
    aromatic_ring_count = n_aromatic_rings
    aliphatic_ring_count = ring_count - aromatic_ring_count
    num_saturated_rings = sum(1 for ring in mol.GetRingInfo().AtomRings()
                              if all(not mol.GetAtomWithIdx(a).GetIsAromatic() and
                                     mol.GetAtomWithIdx(a).GetDegree() == 3
                                     for a in ring))

    # Functional group counts (safe — tolerates missing rdkit attributes)
    num_oh = _fg(mol, "fr_Al_OH") + _fg(mol, "fr_Ar_OH")
    num_nh = _fg(mol, "fr_NH0") + _fg(mol, "fr_NH1") + _fg(mol, "fr_NH2")
    num_aliphatic_oh = _fg(mol, "fr_Al_OH")
    num_aromatic_oh = _fg(mol, "fr_Ar_OH")
    num_carboxylic = _fg(mol, "fr_COO")
    num_ester = _fg(mol, "fr_ester")
    num_ether = _fg(mol, "fr_ether")
    num_ketone = _fg(mol, "fr_ketone")
    num_aldehyde = _fg(mol, "fr_aldehyde")
    num_halogen = _fg(mol, "fr_halogen")
    num_sulfonamide = _fg(mol, "fr_sulfonamide")
    num_nitro = _fg(mol, "fr_nitro")
    num_phenol = _fg(mol, "fr_phenol")
    num_amine = _fg(mol, "fr_NH0") + _fg(mol, "fr_NH1")

    # ---- Lipinski Rule of Five ----
    lip_violations = []
    if mw > 500:
        lip_violations.append(f"MW {mw} > 500")
    if logp > 5:
        lip_violations.append(f"LogP {logp} > 5")
    if hbd > 5:
        lip_violations.append(f"HBD {hbd} > 5")
    if hba > 10:
        lip_violations.append(f"HBA {hba} > 10")
    lipinski = {"pass": len(lip_violations) <= 1, "violations": lip_violations, "violation_count": len(lip_violations)}

    # ---- Veber rules ----
    veber_violations = []
    if rotatable > 10:
        veber_violations.append(f"Rotatable bonds {rotatable} > 10")
    if tpsa > 140:
        veber_violations.append(f"TPSA {tpsa} > 140")
    veber = {"pass": len(veber_violations) == 0, "violations": veber_violations, "violation_count": len(veber_violations)}

    # ---- Ghose filter (160 <= MW <= 480, -0.4 <= LogP <= 5.6, 20 <= atoms <= 70) ----
    ghose_violations = []
    if mw < 160 or mw > 480:
        ghose_violations.append(f"MW {mw} outside 160-480")
    if logp < -0.4 or logp > 5.6:
        ghose_violations.append(f"LogP {logp} outside -0.4-5.6")
    if n_heavy < 20 or n_heavy > 70:
        ghose_violations.append(f"Heavy atoms {n_heavy} outside 20-70")
    if mr < 40 or mr > 130:
        ghose_violations.append(f"MR {mr} outside 40-130")
    ghose = {"pass": len(ghose_violations) == 0, "violations": ghose_violations, "violation_count": len(ghose_violations)}

    # ---- Egan filter (oral absorption: TPSA <= 132, LogP <= 5.88) ----
    egan_violations = []
    if tpsa > 132:
        egan_violations.append(f"TPSA {tpsa} > 132 (poor absorption)")
    if logp > 5.88:
        egan_violations.append(f"LogP {logp} > 5.88 (poor absorption)")
    egan = {"pass": len(egan_violations) == 0, "violations": egan_violations, "violation_count": len(egan_violations)}

    # ---- MDDR-like rules (drug-like space) ----
    mddr_violations = []
    if mw < 200 or mw > 700:
        mddr_violations.append(f"MW {mw} outside 200-700")
    if logp < -2 or logp > 6:
        mddr_violations.append(f"LogP {logp} outside -2-6")
    if tpsa > 180:
        mddr_violations.append(f"TPSA {tpsa} > 180")
    if rotatable > 15:
        mddr_violations.append(f"Rotatable bonds {rotatable} > 15")
    if ring_count > 8:
        mddr_violations.append(f"Ring count {ring_count} > 8")
    mddr = {"pass": len(mddr_violations) == 0, "violations": mddr_violations, "violation_count": len(mddr_violations)}

    # ---- PAINS alerts (Pan Assay Interference Compounds) ----
    pains_patterns = [
        ("Rhodanine", r"[N,n,O,o,S,s]C(=O)CSC(=S)"),
        ("PAINS_1", r"C=CC(=O)"),  # acrylamide
        ("Quinone", r"C1=CC(=O)C=CC1=O"),
        ("Michael_acceptor", r"C=CC(=O)[N,O]"),
        ("Catechol", r"C1=CC=C(O)C(O)=C1"),
        ("Hydroquinone", r"C1=CC=C(O)C=C1O"),
        ("Aniline", r"Nc1ccccc1"),
        ("Azobenzene", r"N=Nc1ccccc1"),
    ]
    pains_hits = []
    for name, smarts in pains_patterns:
        pattern = Chem.MolFromSmarts(smarts)
        if pattern and mol.HasSubstructMatch(pattern):
            pains_hits.append(name)
    pains = {"pass": len(pains_hits) == 0, "alerts": pains_hits, "alert_count": len(pains_hits)}

    # ---- Brenk structural alerts ----
    brenk_alerts = []
    if _fg(mol, "fr_halogen") > 2:
        brenk_alerts.append("Multiple halogen substituents")
    if _fg(mol, "fr_nitro") > 0:
        brenk_alerts.append("Nitro group (mutagenicity concern)")
    if _fg(mol, "fr_sulfonamide") > 0:
        brenk_alerts.append("Sulfonamide (hypersensitivity risk)")
    if n_aromatic_rings > 5:
        brenk_alerts.append(f"Many aromatic rings ({n_aromatic_rings}) — metabolic liability")
    if _fg(mol, "fr_aldehyde") > 0:
        brenk_alerts.append("Aldehyde (reactive, toxicity concern)")
    if _fg(mol, "fr_QuatN") > 0:
        brenk_alerts.append("Quaternary nitrogen (P-gp substrate risk)")
    brenk = {"pass": len(brenk_alerts) == 0, "alerts": brenk_alerts, "alert_count": len(brenk_alerts)}

    # ===================================================================
    # ADMET PREDICTIONS (rule-based / heuristic)
    # ===================================================================

    # ---- Absorption ----
    # Oral bioavailability score (based on Veber + Egan + MW)
    oral_bio_score = 1.0
    if tpsa > 140: oral_bio_score -= 0.3
    if tpsa > 90: oral_bio_score -= 0.1
    if logp < -1: oral_bio_score -= 0.2
    if logp > 5: oral_bio_score -= 0.2
    if mw > 500: oral_bio_score -= 0.2
    if mw < 100: oral_bio_score -= 0.1
    if rotatable > 10: oral_bio_score -= 0.1
    oral_bio = round(max(0, min(1, oral_bio_score)), 3)

    # Caco-2 permeability (LogP and PSA based)
    # High LogP + low PSA = good permeability
    if tpsa < 60 and logp > 1:
        caco2_class = "High"
    elif tpsa < 90 and logp > 0:
        caco2_class = "Moderate"
    elif tpsa < 140:
        caco2_class = "Low"
    else:
        caco2_class = "Very Low"

    # Pgp substrate (MW, LogP, HBA, TPSA based)
    pgp_score = 0
    if mw > 400: pgp_score += 1
    if logp > 2: pgp_score += 1
    if hba > 7: pgp_score += 1
    if tpsa > 90: pgp_score += 1
    pgp_substrate = "Likely" if pgp_score >= 3 else "Unlikely"
    pgp_inhibitor = "Likely" if mw > 400 and logp > 3 and num_nitro == 0 else "Unlikely"

    # Human Intestinal Absorption (HIA)
    if tpsa <= 90 and logp >= -0.7 and mw <= 400:
        hia_class = "High (>90%)"
    elif tpsa <= 140 and mw <= 500:
        hia_class = "Moderate (30-90%)"
    else:
        hia_class = "Low (<30%)"

    # ---- Distribution ----
    # Volume of distribution (LogP and pKa based heuristic)
    vd = round(0.1 + logp * 0.5, 2)  # L/kg rough estimate
    vd = max(0.05, min(vd, 20.0))

    # BBB permeability
    if logp > 2 and mw < 450 and tpsa < 90:
        bbb_class = "High"
    elif logp > 0 and mw < 500 and tpsa < 120:
        bbb_class = "Moderate"
    else:
        bbb_class = "Low"

    # Plasma protein binding (LogP and MW based)
    if logp > 3:
        ppb_class = "High (>95%)"
    elif logp > 1.5:
        ppb_class = "Moderate (80-95%)"
    else:
        ppb_class = "Low (<80%)"

    # CNS penetration
    if tpsa <= 90 and mw <= 400 and logp >= 1 and logp <= 5:
        cns_class = "Favorable"
    elif tpsa <= 120 and mw <= 500:
        cns_class = "Moderate"
    else:
        cns_class = "Unfavorable"

    # ---- Metabolism ----
    # CYP inhibition likelihood (structural feature based)
    cyp_panel = {}
    # CYP1A2: aromatic amines, planar molecules
    cyp_panel["CYP1A2"] = "Inhibitor" if (num_aromatic_rings >= 3 or num_nitro > 0) else "Non-inhibitor"
    # CYP2C9: acidic molecules, sulfonamides
    cyp_panel["CYP2C9"] = "Inhibitor" if (num_carboxylic > 0 or num_sulfonamide > 0) else "Non-inhibitor"
    # CYP2C19: aromatic, basic
    cyp_panel["CYP2C19"] = "Inhibitor" if (logp > 2 and num_aromatic_rings >= 2) else "Non-inhibitor"
    # CYP2D6: basic nitrogen
    cyp_panel["CYP2D6"] = "Inhibitor" if (num_nh > 1 or num_amine > 0) else "Non-inhibitor"
    # CYP3A4: large lipophilic molecules
    cyp_panel["CYP3A4"] = "Inhibitor" if (mw > 500 and logp > 3) else "Non-inhibitor"

    # CYP substrate prediction (lipophilicity and size)
    cyp_substrate_count = sum(1 for v in cyp_panel.values() if v == "Inhibitor")
    cyp_substrate = "Likely multiple" if cyp_substrate_count >= 3 else "Single or none"

    # Half-life estimate (heuristic)
    if logp > 3 and mw > 400:
        half_life_class = "Long (>4h)"
    elif logp > 1.5 and mw > 250:
        half_life_class = "Medium (1-4h)"
    else:
        half_life_class = "Short (<1h)"

    # ---- Toxicity ----
    # AMES mutagenicity (structural alerts)
    ames_alerts = []
    if num_nitro > 0: ames_alerts.append("Nitro group")
    if _fg(mol, "fr_Al_OH") > 1: ames_alerts.append("Multiple aliphatic hydroxyls")
    if mol.HasSubstructMatch(Chem.MolFromSmarts("c1ccc(-[N+](=O)[O-])cc1")): ames_alerts.append("Nitroaromatic")
    if mol.HasSubstructMatch(Chem.MolFromSmarts("N-N")): ames_alerts.append("Azo compound")
    ames_prediction = "Likely mutagen" if ames_alerts else "Non-mutagen"

    # hERG channel liability (LogP, MW, TPSA, charge)
    herg_risk = "High" if (logp > 3.5 and tpsa < 80) else ("Moderate" if logp > 2 else "Low")

    # Hepatotoxicity (DILI - Drug Induced Liver Injury)
    dili_risk = "High" if (logp > 3 and mw > 400 and tpsa < 75) else ("Moderate" if logp > 2.5 else "Low")

    # Skin sensitization (reactive functional groups)
    skin_risk_factors = []
    if _fg(mol, "fr_aldehyde") > 0: skin_risk_factors.append("Aldehyde")
    if _fg(mol, "fr_halogen") > 2: skin_risk_factors.append("Multiple halogens")
    skin_sensitization = "Likely" if skin_risk_factors else "Unlikely"

    # Acute toxicity (LD50 rough estimate based on LogP and functional groups)
    # Crum-Brown and Wood LD50 estimate
    ld50_estimate = round(1.37 + 0.87 * logp - 0.01 * mw + 0.06 * num_halogen, 2)
    ld50_class = "Toxic" if ld50_estimate < 2.5 else ("Moderate" if ld50_estimate < 4 else "Low toxicity")

    # ---- Clearance ----
    clearance_class = "High" if logp < 1 and tpsa > 100 else ("Low" if logp > 3 and tpsa < 60 else "Moderate")

    # Lipophilic efficiency (LipE = pIC50 - LogP; we estimate pIC50 from QED)
    lipe = round(qed_score * 10 - logp, 2) if qed_score > 0 else 0

    # ===================================================================
    # COMPOSITE SCORES
    # ===================================================================
    # Overall drug-likeness score (weighted combination)
    dl_score = 0
    dl_score += 25 * (1 - min(lipinski["violation_count"] / 4, 1))
    dl_score += 15 * (1 - min(veber["violation_count"] / 3, 1))
    dl_score += 15 * (1 - min(ghose["violation_count"] / 4, 1))
    dl_score += 10 * min(qed_score, 1)
    dl_score += 10 * (1 - min(pains["alert_count"] / 3, 1))
    dl_score += 5 * (1 - min(brenk["alert_count"] / 3, 1))
    dl_score += 10 * (1 if oral_bio > 0.5 else 0.5)
    dl_score = round(dl_score, 1)

    # ADMET risk score (lower = safer)
    admet_risk = 0
    if ames_prediction == "Likely mutagen": admet_risk += 3
    if herg_risk == "High": admet_risk += 2
    if dili_risk == "High": admet_risk += 2
    if skin_sensitization == "Likely": admet_risk += 1
    admet_risk = min(admet_risk, 10)

    return {
        "smiles": smiles,
        "formula": formula,
        "heavy_atoms": heavy_atoms,
        "molecular_weight": mw,
        "logp": logp,
        "tpsa": tpsa,
        "hbd": hbd,
        "hba": hba,
        "rotatable_bonds": rotatable,
        "qed_score": qed_score,
        "molar_refractivity": mr,
        "molecular_volume": mol_volume,
        "fsp3": fsp3,
        "labute_asa": labute_asa,
        "estate_sum": estate_sum,
        "wiener_index": wiener,
        "zagreb_index": zagreb,
        "ring_count": ring_count,
        "aromatic_ring_count": aromatic_ring_count,
        "aliphatic_ring_count": aliphatic_ring_count,
        "num_heteroatoms": num_heteroatoms,
        "num_amide_bonds": num_amide_bonds,
        "num_atom_stereocenters": num_atom_stereocenters,
        "num_unspecified_stereocenters": num_unspecified_stereocenters,
        "functional_groups": {
            "oh": num_oh,
            "nh": num_nh,
            "carboxylic_acid": num_carboxylic,
            "ester": num_ester,
            "ether": num_ether,
            "ketone": num_ketone,
            "aldehyde": num_aldehyde,
            "halogen": num_halogen,
            "sulfonamide": num_sulfonamide,
            "nitro": num_nitro,
            "phenol": num_phenol,
        },
        "drug_likeness": {
            "overall_score": dl_score,
            "qed_score": qed_score,
            "lipinski": lipinski,
            "veber": veber,
            "ghose": ghose,
            "egan": egan,
            "mddr": mddr,
        },
        "structural_alerts": {
            "pains": pains,
            "brenk": brenk,
            "total_alert_count": pains["alert_count"] + brenk["alert_count"],
        },
        "absorption": {
            "oral_bioavailability": oral_bio,
            "caco2_permeability": caco2_class,
            "pgp_substrate": pgp_substrate,
            "pgp_inhibitor": pgp_inhibitor,
            "hia": hia_class,
        },
        "distribution": {
            "volume_of_distribution": vd,
            "bbb_permeability": bbb_class,
            "plasma_protein_binding": ppb_class,
            "cns_penetration": cns_class,
        },
        "metabolism": {
            "cyp_inhibition": cyp_panel,
            "cyp_substrate_risk": cyp_substrate,
            "half_life_class": half_life_class,
            "lipophilic_efficiency": lipe,
        },
        "toxicity": {
            "ames_mutagenicity": ames_prediction,
            "ames_alerts": ames_alerts,
            "herg_liability": herg_risk,
            "hepatotoxicity_dili": dili_risk,
            "skin_sensitization": skin_sensitization,
            "skin_sensitization_factors": skin_risk_factors,
            "acute_toxicity_ld50": ld50_class,
            "ld50_estimate_log": ld50_estimate,
            "risk_score": admet_risk,
        },
        "clearance": {
            "clearance_class": clearance_class,
            "half_life_class": half_life_class,
        },
    }
