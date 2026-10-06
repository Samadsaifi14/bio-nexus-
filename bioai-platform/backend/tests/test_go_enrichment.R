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

# Mixed namespaces, versioned Ensembl IDs and alias fallback retain row-level evidence.
db <- get("org.Hs.eg.db", envir = asNamespace("org.Hs.eg.db"))
mixed <- resolve_gene_ids(c("TP53", "7157", "ENSG00000141510.18", "not_a_gene"), db)
stopifnot(all(mixed$entrez_id[1:3] == "7157"), is.na(mixed$entrez_id[4]))
a <- AnnotationDbi::select(db, keys = "7157", keytype = "ENTREZID", columns = "ALIAS")
alias_candidates <- setdiff(a$ALIAS, AnnotationDbi::keys(db, keytype = "SYMBOL"))
recovered <- resolve_gene_ids(alias_candidates, db)
stopifnot(any(recovered$mapping_route == "ALIAS" & recovered$entrez_id == "7157", na.rm = TRUE))
strict <- resolve_gene_ids(alias_candidates, db, aliases = FALSE)
stopifnot(all(is.na(strict$entrez_id)))

out <- tempfile(); dir.create(out)
# Custom database allows documented non-model species with exact IDs.
gmt <- file.path(out, "sets.gmt")
writeLines(c(paste(c("term1", "signal", paste0("g", 1:10)), collapse = "\t"),
             paste(c("term2", "background", paste0("g", 11:30)), collapse = "\t")), gmt)
res <- data.frame(gene = paste0("g", 1:30), padj = c(rep(.001, 10), rep(.5, 20)),
                  direction = c(rep("UP", 10), rep("NS", 20)), stat = 30:1, pvalue = rep(.01, 30))
status <- run_go_enrichment(res, "Test species", out, .05, function(...) {}, database = "CUSTOM",
                          gmt_path = gmt, database_label = "Fixture v1", namespace = "locus_tag")
stopifnot(status$status == "SUCCEEDED", status$background_genes == 30L)
# Rank-sum uses all eligible signed statistics and corrects across both directions.
sets <- read_gene_sets(gmt)
scores <- setNames(res$stat, res$gene)
r <- ranked_gene_sets(scores, sets$sets, sets$terms, .05)
expected <- wilcox.test(30:21, 20:1, alternative = "greater", exact = FALSE, correct = TRUE)$p.value
stopifnot(nrow(r) == 4L, isTRUE(all.equal(r$pvalue[r$go_id == "term1" & r$direction == "UP"], expected)),
          all(r$padj == p.adjust(r$pvalue, "BH")))
tied_scores <- setNames(rep(1:10, each=3), res$gene)
tied <- ranked_gene_sets(tied_scores, sets$sets, sets$terms, .05)
expected_ties <- wilcox.test(tied_scores[1:10], tied_scores[11:30], alternative="less", exact=FALSE, correct=TRUE)$p.value
stopifnot(isTRUE(all.equal(tied$pvalue[tied$go_id == "term1" & tied$direction == "DOWN"], expected_ties)))
null <- ranked_gene_sets(setNames(rep(1,30),res$gene), sets$sets, sets$terms, .05)
stopifnot(all(null$pvalue == 1), all(!null$significant))
status <- run_go_enrichment(res, "Test species", out, .05, function(...) {}, database = "CUSTOM", method = "ranked_wilcoxon",
                          gmt_path = gmt, database_label = "Fixture v1", namespace = "locus_tag")
stopifnot(status$status == "SUCCEEDED", file.exists(file.path(out, "go_ranked_statistics.tsv")))
# One-to-many mapping is excluded; never expand one observed gene into two draws.
mapping <- file.path(out, "mapping.tsv")
write.table(data.frame(source_id = c(res$gene, "g1"), target_id = c(res$gene, "g2")), mapping, sep="\t", quote=FALSE,row.names=FALSE)
status <- run_go_enrichment(res, "Test species", out, .05, function(...) {}, database = "CUSTOM",
                          gmt_path = gmt, mapping_path = mapping, database_label = "Fixture v1", namespace = "locus_tag")
audit <- read.delim(file.path(out,"go_gene_mapping.tsv"))
stopifnot(status$genes_ambiguous == 1L, !audit$in_background[1], status$background_genes == 29L)
# Opposing DEG rows mapped to one target stay in background but leave both query sets.
write.table(data.frame(source_id=res$gene, target_id=c("g1", "g1", res$gene[-c(1,2)])), mapping, sep="\t", quote=FALSE,row.names=FALSE)
conflicted <- res; conflicted$direction[2] <- "DOWN"
status <- run_go_enrichment(conflicted, "Test species", out, .05, function(...) {}, database="CUSTOM",
  gmt_path=gmt, mapping_path=mapping, database_label="Fixture v1", namespace="locus_tag")
stopifnot(status$direction_conflicts == 1L)
# Exercise the production saved-results runner and all figure formats.
result_path <- file.path(out, "results.tsv")
write.table(res, result_path, sep="\t", quote=FALSE, row.names=FALSE)
config_path <- file.path(out, "options.json")
write(jsonlite::toJSON(list(organism="Test species", database="CUSTOM", method="ora", id_type="auto", aliases=TRUE,
  database_label="Fixture v1", namespace="locus_tag", gmt_path=gmt, mapping_path="", alpha=.05), auto_unbox=TRUE), config_path)
retry_out <- file.path(out, "retry")
code <- system2(file.path(R.home("bin"), "Rscript"), c("app/rnaseq/enrichment_retry.R", result_path, config_path, retry_out))
stopifnot(code == 0L)
for (file in c("go_enrichment.svg", "go_enrichment.pdf", "go_enrichment.png", "go_enrichment_all.tsv"))
  stopifnot(file.info(file.path(retry_out,file))$size > 0)
# Invalid custom databases fail clearly.
writeLines("term1\tmissing_genes", gmt)
stopifnot(inherits(try(read_gene_sets(gmt),silent=TRUE), "try-error"))
writeLines(rep("term1\tduplicate\tg1",2), gmt)
stopifnot(inherits(try(read_gene_sets(gmt),silent=TRUE), "try-error"))
unlink(out, recursive = TRUE)
cat("Enrichment recovery and alternate-method tests passed\n")
