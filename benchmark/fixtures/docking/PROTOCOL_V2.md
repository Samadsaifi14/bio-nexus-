# Docking method v2 — declared before comparative execution

Status: implemented; the ligand-aware box rule is covered by unit tests. The original v1 panel remains the baseline.

## Selection, preparation and ranking

- Use only the first deposited model. Explicit receptor-chain selection is optional; when supplied, require every named chain. Filter altlocs to blank/A. Exclude waters and other ligands by default. Retain only explicitly selected cofactor residue instances; record retained/excluded identities and atom counts. Never infer a cofactor from the reference ligand position.
- Prepare benchmark ligand chemistry from official CCD atom names, bond orders and charges at deposited coordinates for every case, including apparently sanitizable perceived graphs. Missing or ambiguous heavy atoms fail preparation. Production SMILES use their own validated molecular graph.
- Search the top five independently ranked fpocket candidates. For each, grow each box dimension to at least the ligand heavy-atom span plus 8 Å, bounded to 40 Å. Record ligand/grid size compatibility; an unrepresentable ligand fails rather than silently shrinking its box. No crystal reference coordinates enter pocket selection or ranking.
- Vina uses seed 42, exhaustiveness 32 and nine modes. Rescore each native pose with Vina's independent Vinardo scoring function at fixed coordinates, without local refinement or pose fitting. Rank all scored poses across searched pockets by Vinardo affinity, then original Vina affinity, then pocket rank/mode for deterministic ties. Retain both scores, all pose identifiers and scoring failures. Vinardo values are model scores, not experimental binding energies.
- Every selected pocket must finish docking and every returned pose must finish rescoring for a complete search. Incomplete searches remain explicit failures, including a timeout. No failed candidate is discarded to produce a green result.

## Evaluation

After the independently ranked result is fixed, evaluate receptor-frame symmetry-aware heavy-atom RMSD. Version 2 evaluates all complete deposited instances of the same CCD ligand, lists each instance's RMSD, and reports the minimum; v1 continues evaluating its original first instance. This accounts for identical occupied receptor copies without moving a pose or choosing a pocket using the reference. A missing/incompatible instance is reported explicitly and cannot be synthesized.

The pose threshold remains <2 Å; panel threshold remains >=70% with an essential control. Version 2 reports its own verdict and never replaces a v1 failure. Each pose's original-mode-1 and revised-rank-1 identities remain distinguishable. Preserve all raw inputs, outputs, logs, source and binary fingerprints. Side-by-side comparisons on this previously examined panel are method-development evidence, not independent external validation or affinity-validation evidence.
