# Docking fixture identity repair

The ten-complex panel retained its PDB IDs but nine noncanonical entries incorrectly named the protein and requested a ligand residue absent from that entry. Corrected against the RCSB deposited structure pages on 18 October 2026:

| PDB | Old residue | Correct deposited residue | Complex |
|---|---|---|---|
| 1STP | BTN | BTN | Streptavidin-biotin |
| 1IEP | STU | STI | Abl kinase-imatinib |
| 1HVR | AHA | XK2 | HIV-1 protease-cyclic urea |
| 2F12 | FU1 | HTM | Sialidase Neu2-inhibitor |
| 1GKC | GSH | NFH | MMP9-reverse hydroxamate |
| 1OYT | MES | FSN | Thrombin-fluorinated inhibitor |
| 1UYG | TIM | PU2 | Hsp90-alpha-purine inhibitor |
| 2H4G | DOG | 694 | PTP1B-thiophene inhibitor |
| 1Q4T | FAD | 4CO | CoA thioesterase-CoA analogue |
| 1P62 | STR | GEO | Deoxycytidine kinase-gemcitabine |

Each fixture entry links to its own RCSB page, for example https://www.rcsb.org/structure/1IEP . Previous run records remain historical evidence of their original inputs. The corrected fixture has its own revision and checksum.

Acceptance criteria are unchanged: top pose symmetry-aware heavy-atom RMSD under 2 A for each panel case, at least 70% overall and at least one existing essential control. The first fpocket site must cover the crystal site; selecting a different site after observing failures is not allowed.

The runner now records the observed deposited ligand inventory, chosen instance, fixture checksum and source PDB even when preparation or grid detection fails. All artifact bytes are fingerprinted for failed as well as passing cases. CI executes both the canonical control and the complete panel, retaining outputs on failure. A completed failed panel is not validation success.

Limitations include discarded cofactors/heteroatoms in the original declared preparation policy, frozen receptors and crystallographic starting ligand coordinates. This is pose-reproduction evidence, not binding-affinity accuracy or blind-screening validation.

The first executed canonical rerun exposed a second harness defect: it interpreted the modern real SDF export as native PDBQT and therefore counted zero models. The runner now consumes only `result_pdbqt`, cross-checks model count with `num_poses`, and archives SDF separately. A missing or inconsistent native artifact fails explicitly. Four regression cases protect the format boundary.
