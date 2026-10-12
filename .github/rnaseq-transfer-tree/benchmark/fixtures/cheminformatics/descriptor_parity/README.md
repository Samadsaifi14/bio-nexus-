{
  "dataset": "BioNexus cheminformatics descriptor-parity set",
  "purpose": "Deterministic exact descriptor parity against a pinned RDKit release over a chemically diverse corpus (MATRIX 3). Predictive/heuristic ADMET evaluation is a separate experiment and is never mixed with this one.",
  "ground_truth_source": "Exact descriptor computation with RDKit 2022.09.5 pinned in expected_descriptors.json. This is reference determinism, not experimental pharmacology.",
  "ground_truth_retrieval": "python benchmark/fixtures/cheminformatics/descriptor_parity/pin_expected.py",
  "diversity_tags": [
    "molecular_size", "charge_state", "zwitterion", "heterocycle", "aromaticity",
    "stereocenters_defined", "stereocenters_unspecified", "geometric_isomerism",
    "ring_fusion", "macrocycle", "difficult_sanitisation", "inorganic_element"
  ],
  "acceptance": "parity: state_permille_exact_match == 1000/1000 AND float_rel_tolerance_all_within over all parseable molecules for the pinned descriptor subset",
  "exclusions": {
    "salts": "SMILES strings are a single covalent species; salt forms are not claimed unless the neutral formula parses.",
    "descriptors_beyond": "Only the pinned descriptor subset is part of the deterministic claim. Labute ASA, 3D descriptors and version-volatile quantities are excluded from the parity contract."
  },
  "synthetic": "no (deterministic reference), but explicitly not biological validation"
}