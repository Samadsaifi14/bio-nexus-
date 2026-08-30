# Bio Nexus Scientific Results Standard

Every analysis result in Bio Nexus should be reviewable at three levels: a concise summary, a scientist-facing evidence view, and the raw machine output. AI interpretation is supplementary and must never replace deterministic scientific results.

## Required result sections

1. **Overview** — analysis status, identifiers, assay/method, high-value metrics and limitations.
2. **QC** — all quality-control metrics with observed value, expected context, PASS/WARN/FAIL state and blocking decision where applicable.
3. **Results** — complete primary scientific output: sortable tables, coordinates, scores, confidence/statistics and appropriate visualizations.
4. **Raw** — original or losslessly represented tool payloads/logs and downloadable artifacts where available.
5. **Methods** — tool and version, parameters, reference/database release, workflow version and reproducibility metadata.
6. **AI interpretation** — optional explanation derived from the evidence above; clearly separated from deterministic results.

## Cross-cutting requirements

- Never infer that a successful process exit means the scientific analysis is valid.
- Preserve warnings and failed records; do not silently discard them.
- Keep reference/database builds explicit and reject incompatible combinations when possible.
- Store tool versions and parameters for reproducibility.
- Display units on quantitative metrics.
- Avoid universal biological QC thresholds where assay-specific interpretation is required.
- Preserve raw evidence behind every summarized metric.
- Mark demonstration/synthetic data conspicuously.

## Minimum outputs by workflow

### NGS
FASTQ/read QC; preprocessing retention; reference/build; mapping/proper-pair/duplicate/MAPQ metrics; depth and breadth of coverage; contamination and identity checks where applicable; variant counts and distributions; filtering reasons; SNV/indel plus SV/CNV when supported; annotation/database versions; prioritized variant evidence; IGV tracks; final readiness gate.

### Molecular dynamics
Structure QC; preparation decisions; force-field/solvent compatibility; minimization; NVT/NPT stability; production settings; energy/temperature/pressure/density when emitted; RMSD/RMSF/Rg/SASA/H-bond/contact analyses when emitted; convergence/sampling assessment; trajectory/artifact provenance. A completed trajectory must not automatically be labelled scientifically converged.

### BLAST
Program/database/version; query metadata; E-value settings; hit count; accession; identity; positives/gaps where applicable; query coverage; bit score; coordinates; HSP alignment; raw/exportable result.

### Alignment and phylogeny
Algorithm/version; scoring/model parameters; sequence/alignment lengths; identity/conservation/gaps; alignment export. Phylogeny additionally records inference method/model, branch lengths, support/bootstrap when available, rooting and Newick.

### Docking
Engine/version; receptor/ligand preparation; search box; seed/exhaustiveness; complete pose table; affinity and RMSD bounds; interaction/contact evidence; raw docking log and pose artifacts.

### ADMET
Input identity and structure; descriptor methods; model/source/version where available; applicability/confidence; complete physicochemical, pharmacokinetic, drug-likeness, alert and toxicity evidence. Heuristic estimates must be labelled as such.

### Primers
Primer sequence, length, Tm, GC%, product size, coordinates, self/hairpin/3-prime complementarity and specificity/off-target evidence when available.

### Structure
Source/method/resolution when experimental; chains/ligands/missing regions; confidence for predicted structures; Ramachandran/clash/secondary-structure metrics when available; downloadable coordinates and source provenance.
