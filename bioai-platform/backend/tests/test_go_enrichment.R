source("app/rnaseq/go_enrichment.R")
universe <- as.character(1:100)
terms <- data.frame(GOID = c("GO:one", "GO:two"), TERM = c("signal", "control"), ONTOLOGY = c("BP", "BP"))
r <- go_ora(list(UP = as.character(1:10), DOWN = character()), universe,
  list("GO:one" = as.character(1:10), "GO:two" = as.character(11:30)), terms, 0.05)
stopifnot(nrow(r) == 2L, r$overlap[r$go_id == "GO:one"] == 10L,
  r$pvalue[r$go_id == "GO:one"] == phyper(9, 10, 90, 10, lower.tail = FALSE),
  r$padj[r$go_id == "GO:one"] == 2 * r$pvalue[r$go_id == "GO:one"],
  r$pvalue[r$go_id == "GO:two"] == 1, sum(r$significant) == 1L)
duplicate <- go_ora(list(UP = c(as.character(1:10), "1")), universe,
  list("GO:one" = as.character(1:10)), terms, 0.05)
stopifnot(duplicate$query_size == 10L)
empty <- go_ora(list(UP = character(), DOWN = character()), universe, list(), terms, 0.05)
stopifnot(nrow(empty) == 0L, all(c("padj", "significant") %in% names(empty)))
res <- data.frame(gene = c("TP53", "BRCA1"), padj = c(0.01, 0.2), direction = c("UP", "NS"))
out <- tempfile(); dir.create(out)
status <- run_go_enrichment(res, "auto", out, 0.05, function(...) stop("Unexpected plot"))
stopifnot(status$status == "NEEDS_ORGANISM")
res$gene <- c("ENSMUSG00000000001", "ENSMUSG00000000002")
status <- run_go_enrichment(res, "human", out, 0.05, function(...) stop("Unexpected plot"))
stopifnot(status$status == "ID_SPECIES_MISMATCH")
# Real local mapping, version stripping, duplicate collapse and DE-eligible background.
res <- data.frame(gene = c("ENSG00000141510.18", "ENSG00000141510.17", "ENSG00000012048.20", "unmapped"),
  padj = c(0.01, 0.02, NA, 0.5), direction = c("UP", "UP", "NS", "NS"))
# Mixed identifier types are unsupported and must not guess symbols as Ensembl.
res$gene <- c("TP53", "TP53", "BRCA1", "NOT_A_REAL_GENE")
status <- run_go_enrichment(res, "human", out, 0.05, function(...) {})
audit <- read.delim(file.path(out, "go_gene_mapping.tsv"))
stopifnot(status$background_genes == 1L, status$genes_uniquely_mapped == 2L,
  status$genes_unmapped == 1L, !audit$in_background[3], !audit$in_background[4])
res$gene <- c("ENSG00000141510.18", "ENSG00000141510.17", "ENSG00000012048.20", "ENSG00000000000.1")
status <- run_go_enrichment(res, "auto", out, 0.05, function(...) {})
stopifnot(status$organism == "human", status$gene_id_type == "ENSEMBL", status$background_genes == 1L)
unlink(out, recursive = TRUE)
cat("GO enrichment statistical and mapping tests passed\n")
