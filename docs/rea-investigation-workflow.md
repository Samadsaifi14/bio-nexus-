# REA investigation workflow

REA 6.4.0 is pinned in `tools/rea`, separate from the production application.
Install with `npm ci --prefix tools/rea`. Preview client changes with
`npm run plan --prefix tools/rea`, then apply authorized registration with
`npm run setup --prefix tools/rea`. Existing configuration is backed up by REA.
Restart the client to load its MCP registration. CLI operations work without
restarting: `npm run rea --prefix tools/rea -- --help`.

This setup installs matching upstream instructions and references. It does not
install a native disassembler or commercial applications. Node.js 24.19.0 and
REA 6.4.0 were used for this implementation. Upstream main's skill version 41
was read; installed release skill version 37 was verified as aligned with its
release. Use the installed command schemas for operations.

## Evidence rules

Use ordinary source tools for complete source repositories, as REA instructs.
Use REA for supplied shipped artifacts or scoped runtime observations. Record
target checksum, tool version, evidence IDs, inspected boundaries and unknowns.
Do not label ordinary source reads or public documentation as REA output.
No proprietary competitor binaries were supplied in this session, so this
release contains independent implementations and a documentation-backed audit,
not binary reconstructions or demonstrated commercial equivalence.

The capability audit is in `docs/competitor-capability-audit.md`. Scientific
acceptance is based on executable regression tests and explicit method identity;
feature resemblance does not establish accuracy, clinical validity or parity.

## Production boundary

REA is developer tooling. Do not expose decompilation, arbitrary process
execution or runtime inspection as public BioNexus API operations. Production
analysis continues through its existing validated input and worker interfaces.

Sources: [REA](https://github.com/morluto/rea),
[installation](https://github.com/morluto/rea/blob/main/docs/installation.md),
[skill](https://github.com/morluto/rea/blob/main/.agents/skills/reverse-engineer-anything/SKILL.md).
