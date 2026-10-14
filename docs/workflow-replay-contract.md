# Portable BioNexus workflow recipes and replay

## Implemented behavior

The owner-authenticated jobs page now exports a built-in protein workflow recipe, imports and validates that recipe JSON, queues a validated recipe on new input, and replays an owned source experiment on its original input. Configuration validation launches no scientific tool. Job submission returns `queued`; execution continues through the existing worker and real pipeline executor. No completed output is synthesized by recipe validation or queueing.

Recipes use `bionexus-workflow-recipe` schema version 1. They allow only the existing protein pipeline's BLAST, UniProt, MSA, phylogeny, domain, enrichment, structure and interpretation steps. Dependencies, unique step identities, alignment modes, BLAST program and maximum hits are validated. Arbitrary commands, unknown tools and extra recipe fields are rejected. The execution entry point preserves selected steps and alignment mode; temporary worker jobs now return collected results and clean up the correct job key.

Source replay checks authoritative job ownership before reading the experiment, normalizes the supplied FASTA through the existing validator, verifies the stored input SHA-256, and requires complete recorded step/BLAST/alignment/fast-mode configuration. Missing configuration is a blocking error, not an inferred default. The newly queued private job retains full input in its authenticated context and original parent job lineage in the same database insert. History preview contains sequence length only.

The replay panel clears a prior plan before a new import/export validation. Failed validation cannot leave an older recipe executable. A request lock prevents duplicate submissions; recipe response revisions and current-job checks prevent stale responses from replacing a new job's plan. Input editing is disabled during submission.

## Evidence and boundaries

REA's skill explicitly routes complete-source architecture analysis to normal repository tools. The independent implementation above follows the existing BioNexus source executor and provenance contracts; it does not claim inspection of proprietary competitor binaries or direct compatibility with their formats. It supplies a bounded workflow reuse/replay capability inspired by workflow platforms, not Galaxy/Seqera/Terra equivalence.

Recipe files contain configuration, not provenance attestations. An imported recipe is untrusted input validated against an allowlist. No source experiment ownership or historical execution is asserted for an imported recipe. Source replay retains parameters but live databases, external providers, software versions and runtime environments may change; identical scientific results are not guaranteed. Galaxy JSON, Nextflow DSL, WDL/CWL import, arbitrary graph editing, durable distributed orchestration and enterprise controls are outside this implementation.

The `parent_job_id` column is defined by `backend/migrations/010_job_history_dag.sql`; that existing migration must be applied in a deployment. Live database migration state and deployed provider execution were not verified in the development environment.

Verification: six new replay/recipe tests cover dependency and command rejection, configuration round-trip, tenant isolation, original-input mismatch rejection, new private queue context and atomic lineage, DNA rejection for protein recipes, and selected-step/alignment propagation with correct result collection and cleanup. Together with evidence-manifest and experiment/provenance tests, 34 tests pass. These use isolated provider/persistence doubles; they establish orchestration and access-control behavior, not a live remote-provider scientific benchmark. TypeScript checks pass.
