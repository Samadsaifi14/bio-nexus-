# BioNexus specialist role briefs

Use only the roles needed for a task. Each role returns concise findings tied to files, tests, and evidence. Portable briefs live here; callable read-only Codex custom-agent profiles live in .codex/agents/. Delegate independent review tasks only. The primary agent owns edits and integration.

## Scientific method reviewer

**Use for:** any change to a scientific method, input contract, evidence class, result status, benchmark, or scientific claim.

**Read:** CODEBASE_MAP.md, SCIENTIFIC_RESULTS_STANDARD.md, the relevant input contract, references, tests, and feature checklist.

**Return:** requested and executed method; assumptions; input/reference identity; parameter and version requirements; validity boundary; concrete positive and negative test cases; exact claim wording supported by evidence.

**Boundary:** do not infer scientific validity from a skill, an API response, integer formatting, a process exit code, or synthetic fixtures. Block invalid downstream analyses and preserve the reason.

## Backend workflow engineer

**Use for:** FastAPI, scientific engines, external retrieval, queues, durable workers, storage, provenance, and exports.

**Read:** the router, service/engine, models, worker dispatch, artifact storage, existing tests, and relevant security controls.

**Return:** exact files and flow changed; failure/retry semantics; idempotency and resource requirements; tests and commands; any deployment configuration needed.

**Boundary:** do not bypass backend result contracts, authentication, quotas, evidence policies, or storage ownership.

## Frontend results engineer

**Use for:** Next.js pages, forms, dashboards, result rendering, plots, and download/share flows.

**Read:** the page, API client, result types, backend response contract, design.md, and UI rules.

**Return:** affected surfaces, loading/partial/error/empty states, accessibility and responsive checks, and screenshots or typecheck/lint results when available.

**Boundary:** render server-emitted scientific values. Do not estimate, renormalize, relabel, or silently replace a scientific value in the browser.

## Security and runtime reviewer

**Use for:** new dependencies, MCP servers, uploaded files, URLs, secrets, external services, execution, and durable storage.

**Read:** SECURITY.md, auth and SSRF controls, runtime/deployment configuration, dependency policies, and relevant workflows.

**Return:** data flow, authority and scope, secrets and network access, resource limits, failure behavior, license, and concrete security tests.

**Boundary:** default to least privilege. Do not send private user data to third parties or make production configuration changes without an explicit product requirement.

## Diagram and documentation editor

**Use for:** architecture, data-flow, provenance, user-journey, or workflow diagrams and their explanatory docs.

**Read:** CODEBASE_MAP.md, source implementation, evidence policy, and the BioNexus diagrams skill.

**Return:** diagram type, source facts, output path, accessibility description, and validation method.

**Boundary:** diagrams explain code and workflow. Scientific plots must be rendered from actual backend-emitted data; never draw illustrative values as if measured.
