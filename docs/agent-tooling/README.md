# Agent tooling for the whole BioNexus repository

This setup is for contributors and coding agents working across sequence analysis, annotation, structure and drug discovery, sequencing, RNA-seq, results, accounts, APIs, and deployment. These repositories improve development work; they are not BioNexus scientific engines.

## Selected setup

| Capability | BioNexus choice | Where it applies |
| --- | --- | --- |
| Codebase map | Graft, generated locally; the tracked CODEBASE_MAP.md remains the shared overview | All frontend, backend, and workflow work |
| Persistent graph alternative | Do not also install Codebase Memory MCP by default; it duplicates code mapping | Reconsider only after a measured Graft gap |
| Specialist agents | Use the small BioNexus role briefs in ROLES.md and callable read-only Codex profiles in .codex/agents/ instead of loading a 48–232-agent collection | Science, architecture, backend, frontend, security, and diagram review |
| MCP tools | Use MCP as a reviewed developer lookup path; follow MCP_POLICY.md | Documentation and public reference lookup across product areas |
| Diagrams | Diagram Design for architecture and explanatory diagrams; use backend-emitted values for actual scientific plots | Architecture, data flow, provenance, study design, and onboarding |
| Scientific skills | Use the project-owned bionexus-science skill plus a reviewed topical skill from K-Dense when needed | BLAST/alignment, annotation, structures, docking, MD, ADMET, NGS, and RNA-seq |
| Video production | OpenMontage is optional for learning or product explainer media only | Education and communications, outside analysis jobs |

## 1. Graft: local code context

Graft builds a regenerable local graph and wires supported coding agents to it. It is not a production dependency and does not replace tests or the shared map.

From a local BioNexus checkout:

1. Install the CLI using the upstream instructions at https://github.com/NanoNets/Graft.
2. Run the dry-run first and inspect every file it proposes to touch.
3. For a Codex CLI setup, use the agents host with no-global so the setup stays repo-scoped: graft init --dry-run, then graft init --agents agents --no-global.
4. Build the local graph and use Graft to target relevant source files. Do not commit its generated graft cache.
5. Keep only the intended repository wiring and review any changes to AGENTS.md before committing.

Graft's benchmark claims are measured by its maintainers on specific models, tasks, and repositories. They are not BioNexus performance results. Use Graft itself for code navigation, not for scientific evidence.

Codebase Memory MCP at https://github.com/DeusData/codebase-memory-mcp is a possible later replacement for a large-repo structural graph. Do not keep both tools active by default.

## 2. Science skills: selective, source-aware use

The broad Scientific Agent Skills collection is at https://github.com/K-Dense-AI/scientific-agent-skills. Do not install the full catalog. Review the exact skill's source, version, license metadata, package requirements, network access, and validation coverage before adding it. The upstream documentation explicitly warns that skills can execute code, install packages, and make network requests.

Start with task-specific candidates such as bulk-rnaseq, experimental-design, biopython, molecular-dynamics, or rdkit. The project-owned skill in .agents/skills/bionexus-science/SKILL.md supplies the BioNexus contracts and routes work across product areas. An upstream skill never overrides those contracts.

For Codex CLI, the upstream project documents selecting individual skills through gh skill install; check that the installed GitHub CLI version supports the command and pin a reviewed release or commit. Installing skill files does not install their scientific dependencies. Use a separate reviewed environment for compute tools; do not modify production dependencies just to make a development skill work.

## 3. Diagrams: explanation versus measured output

The list's diagram repository has grown beyond its original 38-type description. The current canonical Codex plugin source is https://github.com/cathrynlavery/diagram-design. Its static HTML/SVG diagrams are suitable for explanatory documentation. Install it through the documented Codex plugin marketplace if that CLI is used:

- codex plugin marketplace add cathrynlavery/diagram-design
- codex plugin add diagram-design@diagram-design

The project skill at .agents/skills/bionexus-diagrams/SKILL.md states the BioNexus output rules. Architecture and workflow diagrams must be based on verified code. Scientific plots, docking poses, expression matrices, and numerical figure panels must come from actual backend results with their original values and provenance. Never use a diagram generator to synthesize measurements.

## 4. Agent roles: small and domain-specific

The lists at https://github.com/VoltAgent/awesome-claude-code-subagents and https://github.com/wshobson/agents are useful sources, but BioNexus does not need hundreds of always-available profiles. The project defines a small set of read-only Codex custom-agent profiles under .codex/agents/ and portable role briefs in ROLES.md. Codex loads project-scoped custom profiles from that directory in trusted local workspaces; use only the roles relevant to a task. They review and report findings while the primary agent remains responsible for edits and integration.

## 5. MCP catalog: discovery, not installation

Awesome MCP Servers at https://github.com/punkpeye/awesome-mcp-servers is a directory, not one server. Apply MCP_POLICY.md before adding a specific server. Product workflows should continue to use the backend's pinned and provenance-recorded integrations; developer MCP calls may help inspect public documentation or metadata.

## 6. OpenMontage: media-only path

OpenMontage at https://github.com/calesthio/OpenMontage may help create optional user education or product explainer videos. Keep it in a separate media workspace. Review its AGENT_GUIDE.md and generated scripts before running them, and use its zero-key voice path only for non-sensitive content. It must not receive user sequences, sample data, credentials, job artifacts, or result exports. Do not add its video or voice dependencies to the application.

## Maintenance

When a tool is adopted or removed, update this file, the relevant skill, and any role that depends on it. Record the repository URL, reviewed ref, license, and local validation date for vendored code or executable dependencies. Re-check upstream installation guidance before updating pinned versions.
