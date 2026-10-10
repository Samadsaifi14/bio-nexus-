# MCP selection policy

Awesome MCP Servers is a discovery catalog, not a single deployable package. A catalog entry is not an endorsement and a server is not automatically safe or suitable for BioNexus.

## Intended scope

MCP servers may support developer-only lookup of public documentation, API schemas, database records, or repository code. Product computation remains in BioNexus backend integrations and scientific engines so the software can control versions, parameters, caching, provenance, validation, and error states.

Existing product sources include EMBL-EBI/NCBI, UniProt, RCSB PDB, AlphaFold DB, InterProScan, Reactome/KEGG, STRING, PubChem, and GEO-related workflows. Prefer the existing integration when it already provides the needed scientific function. Do not create a second untracked route for the same result.

## Review checklist for every named server

Before adding one to a coding agent or deployment, record:

- Exact repository, owner, commit or release, maintainer activity, and license.
- Whether it is read-only or can write, run commands, browse arbitrary URLs, or access local files.
- Every network destination and credential required; whether secrets are stored outside the repo.
- Whether user sequences, clinical metadata, or uploaded files leave the machine.
- Timeout, retry, rate limit, size limit, logging, cache, and deletion behavior.
- How returned identifiers and claims are verified against the official source.
- How the server is tested, disabled, updated, and removed.

Use read-only and least-privilege scopes. Never expose secrets through prompts or logs. Do not transmit user data unless the user has explicitly approved the data flow and the relevant privacy terms have been reviewed.

## Result boundary

MCP output is external retrieval evidence, not a BioNexus-computed result. Validate the source, accession, database release, payload, and citations. Wrap an adopted value in the BioNexus result contract with a suitable evidence class; preserve uncertainty and retrieval time. If the source cannot be verified, do not present it as a validated result.
