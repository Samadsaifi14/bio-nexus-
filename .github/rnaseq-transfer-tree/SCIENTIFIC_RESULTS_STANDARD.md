# BioNexus Scientific Results Standard

## Non-negotiable result contract

Every scientific backend MUST emit a `ScientificResult` object. The scientific backend is authoritative for scientific values; frontend components may format values and choose presentation, but **must not invent, recalculate, rename, fill, reinterpret, or silently substitute a scientific result**.

```json
{
  "status": "VALID | DEGRADED | NOT_EVALUATED | FAILED",
  "method": "...",
  "engine": "...",
  "engine_version": "...",
  "database": "...",
  "database_version": "...",
  "parameters": {},
  "input_sha256": "...",
  "output_sha256": "...",
  "fallback_used": false,
  "fallback_method": null,
  "results": {},
  "plots": [],
  "artifacts": [],
  "evidence_class": "...",
  "validation": {},
  "citations": []
}
```

The canonical backend implementation lives in `bioai-platform/backend/app/science/result.py`. During migration, a module that has not yet adopted the contract must remain identified as such in the Scientific Validation Registry; absence of a field must never be repaired by a frontend-side estimate.

## Status semantics

- **VALID** — the requested scientific method executed successfully and the emitted result passed the method-specific validation checks that are implemented for the run. This does not by itself mean that the method has been biologically or clinically validated.
- **DEGRADED** — a declared fallback or limitation changed what was executed. The executed method and reason must be explicit. A degraded result may not be presented under the requested method's label.
- **NOT_EVALUATED** — the computation or source result may exist, but the benchmark required for the claimed validation/accuracy statement has not been run or retained.
- **FAILED** — scientific processing stopped. Downstream scientific outputs that depend on the failed step must not be constructed.

A process exit code of zero is not sufficient to label a scientific result `VALID`.

## Fallback rule

A fallback must be scientifically real and provenance-preserving. If `Requested: Clustal Omega` executes MAFFT, the result must record `method=MAFFT`, `fallback_used=true`, the fallback reason, and a `DEGRADED` status. If an aligner fails and no real aligner executes, variant calling and consensus construction must stop. A placeholder, parser default, zero-filled array, synthetic substitute, or heuristic must never be inserted into a field labelled as another method's output.

## Evidence classes

Use one of the platform evidence classes where applicable: Deterministic computation; Reference retrieval; Evidence-backed inference; Heuristic; AI-generated interpretation; Experimental observation; Benchmark result; Unsupported/insufficient evidence.

AI-generated text is always downstream of deterministic/reference evidence. Grounding validation may establish correspondence to recorded evidence; it does not independently establish biological truth.

## Required result views

Every result should be reviewable at three levels: concise summary, scientist-facing evidence, and raw/source output. AI interpretation is supplementary and must never replace deterministic scientific results.

1. **Overview** — scientific status, method, identifiers, high-value metrics and limitations.
2. **QC** — quality-control metrics with observed value, context, state and blocking decision where applicable.
3. **Results** — complete primary scientific output: tables, coordinates, scores, confidence/statistics and appropriate visualizations.
4. **Raw** — original or losslessly represented tool payloads/logs and downloadable artifacts where permitted.
5. **Methods** — tool/version, parameters, reference/database release, workflow version and reproducibility metadata.
6. **AI interpretation** — optional explanation derived only from the evidence above and clearly separated from deterministic results.

## Cross-cutting requirements

- Preserve warnings and failed records; do not silently discard them.
- Keep reference/database builds explicit and reject incompatible combinations when possible.
- Store exact tool versions and parameters.
- Display units on quantitative metrics.
- Avoid universal biological QC thresholds where assay-specific interpretation is required.
- Preserve raw evidence behind every summarized metric.
- Mark demonstration/synthetic data conspicuously.
- Reject NaN/Infinity before tables, plots, JSON or downloads are emitted.
- **No data = no graph.** Never replace absent scientific data with `(0,0)`, zero bars, or a fabricated trace.
- The downloadable full result must remain the authoritative complete calculation when the UI down-samples a display.
- Missing evidence is not a negative biological finding.

## Scientific Validation Registry

The registry in `bioai-platform/backend/app/science/validation_registry.py` is separate from per-run `ScientificResult.status`. A module can be software/method verified while production accuracy remains `NOT_EVALUATED`.

`VALIDATED` is benchmark-gated. Runtime/UI/AI code cannot promote it. A promotion requires an integrity-checked evidence artifact under `benchmarks/validation-registry` containing the benchmark identifier, run identifier, predeclared acceptance criteria and retained results.

## Minimum outputs by workflow

### Consensus sequencing
FASTQ QC; exact aligner/version/parameters; mapping QC; base-quality and mapping-quality filters; per-position depth; strand counts; allele fractions; indel handling; low-coverage masking; consensus FASTA; variant table/VCF; alignment artifact where applicable; provenance JSON. If alignment fails, variant calling and consensus construction stop.

### NGS
FASTQ/read QC; preprocessing retention; reference/build; mapping/proper-pair/duplicate/MAPQ metrics; depth and breadth of coverage; contamination and identity checks where applicable; variant counts and distributions; filtering reasons; SNV/indel plus SV/CNV when supported; annotation/database versions; prioritized variant evidence; IGV tracks; final readiness gate. Production accuracy stays `NOT_EVALUATED` until a BioNexus-produced callset is evaluated against a matching accepted truth set/confident regions.

### RNA-seq
Input/read QC; sample metadata/design; exact workflow/tool versions; retained count/quantification matrix; normalization/model parameters; PCA/sample-distance evidence; full DEG table; volcano/MA/heatmap generated from the retained matrices/tables; point-to-row-to-count/sample traceability; complete exports and provenance.

### Molecular dynamics
Structure QC; preparation decisions; force-field/solvent compatibility; minimization; equilibration; production settings; energy/temperature/pressure/density when emitted; RMSD/RMSF/Rg/SASA/H-bond/contact analyses when emitted; convergence/sampling assessment; trajectory/artifact provenance. Current hosted implicit-solvent OpenMM must not be represented as equivalent to a validated explicit-solvent production protocol.

### BLAST
Program/database/version or database date; query metadata; E-value settings; hit count; accession; description; identity; positives/gaps where applicable; query coverage; bit score; coordinates; alignment length; complete HSP strings; normalized table/JSON and raw source response/report when permitted.

### Alignment and phylogeny
Requested and executed algorithm/version; fallback provenance; scoring/model parameters; sequence/alignment lengths; identity/conservation/gaps; alignment export. Phylogeny additionally records inference method/model, branch lengths, bootstrap/support statistics, seed, rooting and Newick. Bootstrap support must not be described as the probability a clade is correct.

### Pocket/cavity analysis
CASTp, fpocket and BioNexus geometric/SASA heuristic are distinct methods. CASTp-labelled fields may contain CASTp output only. fpocket results must expose fpocket scores/druggability-related outputs, volume, alpha-sphere/residue evidence when available. Heuristic results are labelled `Heuristic` and never substituted for CASTp/fpocket values.

### Docking
Engine/version; scoring function; receptor/ligand and their preparation; search box; seed/exhaustiveness/num_modes/energy_range/CPU; complete pose table; affinity and RMSD bounds; interaction/contact evidence; raw log/config and receptor/ligand/pose artifacts. Redocking thresholds must be declared before evaluating the result.

### ADMET
Separate deterministic calculated descriptors, rule-based screening and model-based predictions. Predictive endpoints require model/version, units, applicability domain and uncertainty. Rule-based alerts must not be presented as validated QSAR or experimental ADMET/toxicity measurements.

### Primers
Primer sequences, coordinates, Tm, GC%, product size, primer/pair penalties, self-complementarity, 3-prime complementarity, hairpin/pair thermodynamics as available; ionic/concentration assumptions and constraints. Template amplification and genome-wide specificity are separate claims.

### Structure
Experimental structures: source/method/resolution and available wwPDB validation metrics. Predicted structures: prediction source/model, per-residue confidence, pLDDT plot, PAE when available and explicit computational-prediction label. Predicted and experimental evidence quality must remain distinct.
