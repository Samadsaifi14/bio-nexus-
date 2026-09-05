# Comparative evaluation protocol

BioNexus comparisons with Galaxy, Nextflow/nf-core, workflow engines, or domain-specific platforms must use predeclared, observable criteria. This protocol prohibits unsupported statements such as “better”, “more accurate”, “easier”, or “more reproducible” unless the exact corresponding measurement supports the wording.

## Evaluation unit

The unit of analysis is a **completed workflow run on the same pinned input and reference set**. Each platform receives the same scientific task and ground truth. Platform versions, wrappers/workflows, execution environment and all deviations are recorded. Multiple runs are required where stochasticity or infrastructure variability matters.

## Objective criteria

Reproducibility measures immutable run identity, input/output checksums, code/workflow version, software/database versions, container/environment capture, random seeds and parameters. Workflow traceability measures ordered steps, dependencies, tool/version records, parameter/database provenance and timestamps. Provenance completeness measures input, computation, AI, figure and export lineage. Failure transparency measures visible failed stages, error causes, partial-result labels and fallback labels. Benchmark coverage counts only fixtures with declared ground truth, acceptance rules, retained raw outputs and retained failures. Export quality measures machine-readable exports, checksums, manifests, RO-Crate/citation metadata and publication-figure metadata. Scientific reporting completeness measures Methods, Results, sample size, statistical method, confidence intervals when applicable, data/code availability and limitations.

## Statistics

Every category must report the number of evaluated runs. For binary completeness fields, report the proportion of runs satisfying each field and an interval estimate when the study has enough runs to make an interval meaningful. Performance/runtime comparisons should report distributions rather than a single best run. Accuracy metrics must use the domain-specific ground truth defined in BBS-2; workflow-output parity is not biological accuracy.

## No composite superiority score

BioNexus intentionally does not emit a single platform ranking from these criteria. Any weighting across reproducibility, runtime, accuracy, reporting completeness or usability is value-laden. The machine-readable evaluator therefore reports category-level fractions and sample sizes while setting `ranking` to null.

## Usability and UI

UI quality, ease of use, learning curve and researcher preference require a separately preregistered user study with participant characteristics, task definitions, success metrics and appropriate statistics. They are outside this automated comparison protocol.

## Publication requirement

A manuscript comparison must publish the exact task definitions, platform/workflow versions, configuration files, raw evaluation records, exclusions, failed runs and evaluation code. Conclusions must be scoped to the tested versions, datasets and tasks.
