source("app/rnaseq/go_enrichment.R")
stopifnot(requireNamespace("fgsea", quietly = TRUE))
set.seed(841)
scores <- setNames(rnorm(200), paste0("g", 1:200))
ordered <- names(sort(scores, decreasing = TRUE))
pathways <- list(positive = ordered[1:20], negative = tail(ordered, 20), null = names(scores)[seq(1, 200, by = 5)])
terms <- data.frame(GOID = names(pathways), TERM = names(pathways), ONTOLOGY = "CUSTOM")
actual <- preranked_gsea(scores, pathways, terms, .05)
ordered_scores <- scores[order(-scores, names(scores))]
set.seed(1729)
expected <- as.data.frame(fgsea::fgseaMultilevel(pathways = pathways, stats = ordered_scores,
  minSize = 10L, maxSize = 500L, eps = 1e-10, sampleSize = 101L, nPermSimple = 1000L,
  nproc = 1L, scoreType = "std", gseaParam = 1))
expected <- expected[match(actual$go_id, expected$pathway), ]
stopifnot(isTRUE(all.equal(actual$NES, expected$NES)),
  isTRUE(all.equal(actual$pvalue, expected$pval)),
  isTRUE(all.equal(actual$padj, p.adjust(expected$pval, "BH"))),
  actual$direction[actual$go_id == "positive"] == "UP",
  actual$direction[actual$go_id == "negative"] == "DOWN",
  identical(actual, preranked_gsea(scores, pathways, terms, .05)))
stopifnot(inherits(try(preranked_gsea(setNames(rep(1, 200), names(scores)), pathways, terms, .05), silent=TRUE), "try-error"))
stopifnot(nrow(preranked_gsea(scores, list(short=names(scores)[1:2]), terms, .05)) == 0)
out <- tempfile(); dir.create(out)
gmt <- file.path(out, "sets.gmt")
writeLines(vapply(names(pathways), function(k) paste(c(k, k, pathways[[k]]), collapse="\t"), character(1)), gmt)
res <- data.frame(gene=names(scores), stat=as.numeric(scores), pvalue=.5, padj=.5, direction="NS")
status <- run_go_enrichment(res, "Fixture organism", out, .05, function(...) {}, database="CUSTOM", method="gsea",
  gmt_path=gmt, database_label="Synthetic sets v1", namespace="fixture gene IDs")
stopifnot(status$status == "SUCCEEDED", status$background_genes == 200,
  status$gsea_parameters$seed == 1729, status$method_key == "gsea", status$fgsea_version == as.character(packageVersion("fgsea")))
audit <- read.delim(file.path(out, "go_gene_mapping.tsv"))
# Genes outside any set stay in the preranked universe.
stopifnot(all(audit$in_background))
written <- read.delim(file.path(out, "go_enrichment_all.tsv"))
stopifnot(all(c("ES", "NES", "log2err", "genes", "padj") %in% names(written)))
cat("Preranked GSEA parity, direction, reproducibility and universe checks passed\n")
