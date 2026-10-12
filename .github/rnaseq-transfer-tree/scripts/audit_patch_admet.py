from __future__ import annotations

from pathlib import Path

# One-shot, idempotent scientific patch used only on the isolated audit branch.
path = Path("bioai-platform/backend/app/tools/admet.py")
text = path.read_text(encoding="utf-8")

replacements = [
    (
        '"""ADMET descriptor computation using RDKit — industrial-grade panel.\n\nComputes 50+ molecular descriptors including:\n  - Core physicochemical properties (MW, LogP, TPSA, HBD, HBA, etc.)\n  - Extended topological descriptors (Fsp3, aromatic rings, MR, volume, complexity)\n  - Drug-likeness filters (Lipinski, Veber, Ghose, Egan, MDDR, PAINS, Brenk)\n  - ADMET predictions (absorption, distribution, metabolism, toxicity, clearance)\n  - Structural alerts and functional group analysis\n"""',
        '"""RDKit molecular descriptors plus explicitly labelled screening heuristics.\n\nDeterministic physicochemical descriptors and established rule filters are kept\nseparate from heuristic ADMET flags.  Heuristic outputs are not presented as\nvalidated QSAR predictions, experimental observations, or clinical evidence.\n"""',
    ),
    (
        '    # SwissADME "H-bond acceptors" = all N + O atoms (OpenBabel count).\n    # CalcNumLipinskiHBA is a pure N+O count; the plain NumHAcceptors /\n    # CalcNumHBA exclude e.g. ester carbonyl oxygens and would show 3 for\n    # aspirin instead of SwissADME\'s 4.\n    hba = rdMolDescriptors.CalcNumLipinskiHBA(mol)',
        '    # Method-specific HBA count.  RDKit exposes multiple accepted HBA\n    # conventions; this API retains CalcNumLipinskiHBA for backward compatibility\n    # and reports that convention explicitly in _descriptor_conventions.\n    hba = rdMolDescriptors.CalcNumLipinskiHBA(mol)',
    ),
    (
        '    # Acute toxicity (LD50 rough estimate based on LogP and functional groups)\n    # Crum-Brown and Wood LD50 estimate\n    ld50_estimate = round(1.37 + 0.87 * logp - 0.01 * mw + 0.06 * num_halogen, 2)\n    ld50_class = "Toxic" if ld50_estimate < 2.5 else ("Moderate" if ld50_estimate < 4 else "Low toxicity")',
        '    # Acute toxicity requires a validated endpoint-specific model or measured\n    # data.  A previous ad-hoc LogP/MW formula produced an unsupported numeric LD50\n    # claim, so BioNexus now withholds this quantity.  ProTox is exposed separately.\n    ld50_estimate = None\n    ld50_class = "Not predicted"\n    acute_toxicity_note = (\n        "No validated local LD50 model is implemented; use the separately labelled "\n        "ProTox integration or experimental data for toxicity prediction."\n    )',
    ),
    (
        '    # Lipophilic efficiency (LipE = pIC50 - LogP; we estimate pIC50 from QED)\n    lipe = round(qed_score * 10 - logp, 2) if qed_score > 0 else 0',
        '    # Lipophilic efficiency (LipE/LLE) requires an experimental or otherwise\n    # justified potency term (e.g. pIC50). QED is not a potency surrogate.\n    lipe = None\n    lipe_note = "LipE requires potency (for example pIC50); it is not derivable from QED and LogP alone."',
    ),
    (
        '    # SWISSADME-PARITY PANEL\n    # ===================================================================\n    # Reproduces the SwissADME output layout for the properties that are\n    # computable with RDKit (WLOGP, ESOL, BOILED-Egg, Martin score, SA…).',
        '    # SWISSADME-STYLE COMPATIBILITY PANEL\n    # ===================================================================\n    # Uses a SwissADME-like layout only for locally reproducible properties.\n    # It is not a SwissADME execution and must not be presented as parity.',
    ),
    (
        '            "note": "ESOL (Delaney) using WLOGP in place of XLOGP3 — values are within ~0.1 log unit of SwissADME for most drug-like molecules.",',
        '            "note": "ESOL-style estimate using WLOGP as the lipophilicity input; this is a local approximation and is not claimed to reproduce SwissADME output.",',
    ),
    (
        '            "structural_alerts": {"tier": "3a", "confidence": "high", "method": "PAINS/Brenk SMARTS patterns", "note": "Well-established substructure filters — production-ready"},',
        '            "structural_alerts": {"tier": "3b", "confidence": "limited", "method": "Local SMARTS screening subset", "note": "Heuristic screening subset; not a complete PAINS/Brenk catalogue and not a toxicity prediction."},',
    ),
    (
        '            "clearance": {"tier": "3b", "confidence": "approximate", "method": "LogP/TPSA heuristic", "note": "Very rough estimate — real clearance depends on CYP metabolism kinetics"},\n        },\n        "heavy_atoms": heavy_atoms,',
        '            "clearance": {"tier": "3b", "confidence": "approximate", "method": "LogP/TPSA heuristic", "note": "Very rough screening flag — real clearance depends on measured/validated pharmacokinetic evidence."},\n        },\n        "_descriptor_conventions": {\n            "molecular_weight": "RDKit Descriptors.MolWt",\n            "logp": "RDKit Wildman-Crippen MolLogP",\n            "tpsa": "RDKit Descriptors.TPSA(includeSandP=True)",\n            "hbd": "RDKit Lipinski.NumHDonors",\n            "hba": "RDKit CalcNumLipinskiHBA",\n            "rotatable_bonds": "RDKit Lipinski.NumRotatableBonds",\n            "qed": "RDKit QED.qed",\n        },\n        "heavy_atoms": heavy_atoms,',
    ),
    (
        '            "lipophilic_efficiency": lipe,\n        },',
        '            "lipophilic_efficiency": lipe,\n            "lipophilic_efficiency_note": lipe_note,\n        },',
    ),
    (
        '            "acute_toxicity_ld50": ld50_class,\n            "ld50_estimate_log": ld50_estimate,\n            "risk_score": admet_risk,',
        '            "acute_toxicity_ld50": ld50_class,\n            "ld50_estimate_log": ld50_estimate,\n            "acute_toxicity_note": acute_toxicity_note,\n            "risk_score": admet_risk,',
    ),
]

for old, new in replacements:
    if old not in text:
        raise SystemExit(f"Expected ADMET source block not found:\n{old[:180]}")
    text = text.replace(old, new, 1)

path.write_text(text, encoding="utf-8")
print(f"patched {path}")
