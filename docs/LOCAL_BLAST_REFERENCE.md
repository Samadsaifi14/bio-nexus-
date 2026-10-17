# Local Swiss-Prot BLAST

The production BlastTool and pipeline try local NCBI BLAST+ first only for blastp against swissprot/uniprotkb_swissprot. Other database/program scopes retain their configured providers. Unavailable local tooling returns no local result; it never masquerades as a completed zero-hit search.

The image provisions the complete canonical Swiss-Prot FASTA from the fixed official UniProt origin, checks release metadata before/after download, builds a BLAST index and records SHA-256 for the source and all index files. Query runs verify that index identity and retain the reference manifest, release, native XML, task, E-value threshold, thread count and BLAST version. A short query uses the documented blastp-short task.

Native integration fixtures are explicitly small test databases. A separate full-snapshot job executes the predeclared eight-accession recovery controls through the production tool and retains raw XML and query hashes. These same-reference positive controls establish routing and accession recovery, not novel-protein function or external NCBI service availability.

Primary method documentation:
- https://www.ncbi.nlm.nih.gov/books/NBK569839/
- https://www.ncbi.nlm.nih.gov/books/NBK279684/
- https://www.uniprot.org/help/downloads

ADMET audit conventions now test both chemical acceptors and the separate Lipinski N+O count. Their numeric definitions are not interchangeable. NCBI polling status tests recognise STUCK as a terminal service outcome, not a successful biological search.
