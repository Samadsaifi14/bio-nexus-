# Executed Sarek evidence boundary

Run this verifier against the authenticated owner's exported executor record
and the actual retained run bundle. It does not launch Nextflow or provision
cloud compute. Without both inputs it emits NOT_EXECUTED, with local runtime
availability, and makes no completed-sequencing claim.

```bash
PYTHONPATH=bioai-platform/backend python benchmark/fixtures/ngs/verify_sarek_execution.py \
  --run-record owned_run_record.json --bundle retained_run_directory
```

The bundle's `execution_evidence.json` must contain `run_id`, `command_sha256`,
`workflow` (`nf-core/sarek`), `revision` (`3.10.0`), `nextflow_version`, `trace`,
and nonempty `inputs`, `references` and `outputs` arrays. Each array item has a
relative `path` and exact file `sha256`. The trace itself must be a checksummed
output and include `name`, `status`, `exit`, and `container` columns. Enable those
trace fields in the reviewed execution configuration. Every process needs its
executed image's immutable `@sha256:` digest; mutable image tags are insufficient.
Keep failed/retried attempts; final attempts must complete successfully.

All required Sarek artifact contracts must be represented. Reference checksums
must include the actual FASTA/indexes, known sites, intervals and relevant
annotation resources, not just the text of a build label. Retain the sample
sheet and source input identities with the worker outputs and reports. The
bundle checker confirms bytes/identities; it does not certify that a reference
is scientifically appropriate or that clinical/biological validation passed.

The local wrapper additionally retains the exact command, command SHA-256,
state transition history, exit state and worker-log checksum. The wrapper's
regression tests execute Python process controls; they are explicitly not
Sarek execution evidence. An actual Sarek run in a configured worker remains
required before reporting completed upstream analyses in manuscript Results.
