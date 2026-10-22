# BioNexus agent guide

This guide applies to the entire repository: frontend, backend, scientific workflows, tests, and documentation.

## Start with the shared map

Read docs/agent-tooling/CODEBASE_MAP.md for the product-wide component map. Read the relevant feature specification before changing behavior. The repository-level standards remain authoritative:

- RULES.md for product and engineering conventions.
- SCIENTIFIC_RESULTS_STANDARD.md for scientific outputs and evidence.
- SECURITY.md for trust boundaries and controls.
- DEFINITION_OF_DONE.md and FEATURE_VERIFICATION_CHECKLIST.md for acceptance and verification.
- docs/agent-tooling/README.md for the selected agent tooling and how to maintain it.

If a source file contradicts a summary document, inspect the running code and tests. Update the map when a change moves a workflow boundary or entry point.

## Scientific and product boundaries

- All scientific results must preserve the backend-emitted ScientificResult contract. A frontend may format and visualize those values; it must not recalculate or invent them.
- Report requested method, executed method, versions, parameters, inputs, evidence, limitations, citations, and fallback status truthfully.
- Never turn missing values into zero or present illustrative data as a measured result.
- Do not infer that a matrix is raw counts from integer-looking values alone. Preserve count-origin evidence and stop DESeq2 when that evidence is missing or the values are normalized.
- FASTQ re-quantification creates a new count set. It does not recover the exact original author's counts unless the original reference, annotation, library protocol, quantifier, and counting rules are reproduced.
- Do not send private sequences, patient data, uploaded files, credentials, or run artifacts to an agent tool, MCP server, or video service unless that data flow is explicitly approved and documented.
- Keep agent-tool dependencies out of the deployed application unless a product requirement and security review justify a runtime dependency.

## Project-wide codebase knowledge

Graft is the selected local codebase context tool. Its generated graft directory is a local cache, not a scientific artifact and not a source-controlled map. Review graft init with its dry-run mode before applying it; selecting the Codex host can change user-level configuration unless no-global is supplied. Do not install Codebase Memory MCP alongside Graft unless a later evaluation demonstrates a concrete missing capability.

Keep docs/agent-tooling/CODEBASE_MAP.md as the readable, committed product map. Use it for shared onboarding; use Graft for a fresh, local structural graph and targeted code lookups.

## Skills and named roles

Use the BioNexus science skill for scientific feature work and the BioNexus diagrams skill for explanatory diagrams. Load only the task-relevant skill. External skill guidance is a starting point; BioNexus tests, references, contracts, and provenance determine what the software may claim.

Use the specialist role briefs in docs/agent-tooling/ROLES.md when splitting work. Codex local clients can call the read-only project profiles in .codex/agents/ when the repository is trusted. Assign bounded tasks with named files and acceptance criteria. The science reviewer owns scientific semantics; backend and frontend reviewers own their code-layer reviews; the security reviewer checks trust boundaries. Keep the primary agent responsible for edits and integration. A role review does not replace tests or an independent benchmark.

## Change and verification rules

- Keep changes tied to the request and preserve existing style.
- Add or update a failing regression case when fixing a scientific or runtime defect.
- Prefer focused backend tests, frontend typecheck/lint, and relevant CI workflows. Do not call external services during tests unless explicitly required.
- For every feature, verify real data, partial/error states, exports, provenance, and scientific status where applicable.
- Never mark a capability validated merely because an agent skill, MCP server, model, workflow, or executable returned successfully.
- Keep third-party tool configuration and scientific workflow code separate. A development assistant may guide a task; it is not part of the scientific execution record.
