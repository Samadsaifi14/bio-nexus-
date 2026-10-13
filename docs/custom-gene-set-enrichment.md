# Custom gene-set enrichment

BioNexus now exposes `POST /api/pathways/enrichment/gene-sets` (the pathways router is mounted under the API prefix). This independent implementation provides a functional-genomics capability inspired by enrichment workflows; it does not reconstruct proprietary OmicsBox code.

Submit `identifiers`, an explicit `background`, `gene_sets` (term ID to identifier list), and mandatory `source`, `release`, `organism`, `identifier_namespace` fields. The background should contain all identifiers eligible for selection in the experiment, such as all genes that passed the differential-expression testing filter, rather than only significant genes.

The service matches identifiers exactly, removes duplicates, rejects a query outside the declared background, intersects annotations with that universe and evaluates one-sided hypergeometric over-representation. Benjamini–Hochberg correction includes every supplied term with at least one background member, including terms with zero overlap; terms with no background members are excluded and counted. All tested rows are returned with overlaps, population counts, raw p-values, adjusted p-values and fold enrichment. Input and annotation SHA-256 digests support replay. The declared database source/release is retained but is not independently authenticated.

No implicit identifier mapping, cross-species projection, ontology ancestor propagation or invented annotation occurs. GO terms must already have the desired ancestor propagation in the submitted mapping. Reactome and g:Profiler enrichment routes retain their existing behavior. The Pathway Analysis page includes a Custom background tab with selected/background identifier inputs, GMT file upload or paste, required provenance fields, a result table and complete JSON/TSV exports. No bundled annotation database is claimed.

Validation: exact combinatorial references for hypergeometric tails, zero-overlap multiple-testing coverage, duplicate handling, query/background rejection, order-invariant digests and endpoint behavior. Resource limits reject excessive memberships or exact-tail work rather than producing approximate results silently.
