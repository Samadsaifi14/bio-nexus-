# BBS-2 DOI deposition procedure

The BioNexus Benchmark Suite should receive a DOI only for an immutable public release that contains the exact benchmark registry snapshot, fixture manifests, checksums, raw run outputs, aggregate statistics, failure analysis and software/database version manifests used in the associated manuscript.

A release is DOI-ready only when all of the following are true:

1. The repository release is tagged and immutable for the manuscript version.
2. `benchmark_repository.json` is included unchanged in the deposit.
3. Every claimed benchmark result has a persisted fixture checksum, output checksum and acceptance decision.
4. Failed cases are included rather than removed from the deposit.
5. The continuous-benchmark reports for the declared operating systems/software versions are archived.
6. The manuscript supplement points to the same release tag and deposit.
7. The deposited archive has its own SHA-256 checksum recorded in the manuscript records.

Recommended release route: connect the public GitHub repository to a DOI-minting archive such as Zenodo, create a versioned GitHub release, allow the archive to ingest that exact release, then record both the version DOI and concept DOI in the benchmark manifest and publication package.

Do not place a fabricated or provisional DOI into BioNexus. Until a DOI has actually been minted, machine-readable metadata must use `doi: null` and `doi_status: not_minted`.
