---
name: bionexus-diagrams
description: Create accessible, source-grounded architecture and workflow diagrams for BioNexus without inventing scientific measurements.
---

# BioNexus diagrams skill

Use the Diagram Design skill for explanatory diagrams when available. The upstream repository is https://github.com/cathrynlavery/diagram-design. It supports static HTML and SVG diagrams and a Codex plugin. For installation and updates, follow its current plugin instructions in docs/agent-tooling/README.md.

## Choose a diagram by the question

- Architecture: show UI, API, worker, storage, and external sources.
- Data flow: show input validation, scientific computation, result contract, plots, exports, and provenance.
- Sequence diagram: show a request, durable job, polling, result persistence, and error/retry behavior.
- Lifecycle: show evidence or artifact status transitions.
- Comparison: put measured, validated platform outputs side by side only when the same workload and evidence are available.
- User journey: show the required user decisions and review gates.

## Source and output rules

- Read the current source files and tests before drawing. Use CODEBASE_MAP.md only as a navigation aid.
- Cite the code paths, study, method, database release, or benchmark source behind the diagram.
- Use actual labels and distinctions from the implementation. Mark unimplemented or unvalidated steps explicitly.
- Keep diagram assets static by default, with an accessible title and text description. Respect reduced motion if motion is necessary.
- Save explanatory diagrams under the relevant docs folder and identify the source and revision.
- Do not use generic stock values or fabricated examples in a scientific plot. Scientific result figures must come from backend-emitted payloads and retain their raw source data, status, evidence class, and provenance.
- Do not describe a visual or a successful rendering as validation of the science.
