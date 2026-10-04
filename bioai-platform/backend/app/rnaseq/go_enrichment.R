# Local GO over-representation analysis. No sample data or gene lists leave the worker.
go_ora <- function(sets, universe, term_genes, terms, alpha) {
  rows <- list()
  for (direction in names(sets)) {
    query <- intersect(unique(sets[[direction]]), universe)
    if (!length(query)) next
    for (term in names(term_genes)) {
      members <- intersect(term_genes[[term]], universe)
      m <- length(members); n <- length(query); N <- length(universe)
      if (m < 10L || m > 500L) next
      hits <- intersect(query, members); k <- length(hits)
      # Include zero-overlap terms in the multiple-testing family.
      rows[[length(rows) + 1L]] <- data.frame(direction = direction, go_id = term,
        term = terms$TERM[match(term, terms$GOID)], ontology = terms$ONTOLOGY[match(term, terms$GOID)],
        overlap = k, query_size = n, term_size = m, universe_size = N,
        fold_enrichment = (k / n) / (m / N),
        pvalue = phyper(k - 1L, m, N - m, n, lower.tail = FALSE),
        genes = paste(sort(hits), collapse = ";"), stringsAsFactors = FALSE)
    }
  }
  if (!length(rows)) return(data.frame(direction = character(), go_id = character(), term = character(),
    ontology = character(), overlap = integer(), query_size = integer(), term_size = integer(),
    universe_size = integer(), fold_enrichment = numeric(), pvalue = numeric(), genes = character(),
    padj = numeric(), significant = logical()))
  result <- do.call(rbind, rows)
  # One BH family across all GO ontologies and both directions.
  result$padj <- p.adjust(result$pvalue, method = "BH")
  result$significant <- result$padj < alpha
  result[order(result$padj, result$pvalue, result$direction, result$go_id), , drop = FALSE]
}

run_go_enrichment <- function(res_df, organism, outdir, alpha, plot_fun) {
  status <- list(status = "NOT_RUN", message = "", organism = organism,
    method = "GO over-representation; one-sided hypergeometric; BH across all terms and directions",
    background = "Genes with non-missing DESeq2 adjusted p-values, uniquely mapped and GO annotated",
    min_term_size = 10L, max_term_size = 500L, alpha = alpha)
  finish <- function() {
    write(jsonlite::toJSON(status, auto_unbox = TRUE, pretty = TRUE, null = "null"),
      file.path(outdir, "go_enrichment_summary.json"))
    status
  }
  ids <- as.character(res_df$gene)
  ensembl <- grepl("^ENS[A-Z]*G[0-9]+(\\.[0-9]+)?$", ids)
  ids[ensembl] <- sub("\\.[0-9]+$", "", ids[ensembl])
  human <- grepl("^ENSG[0-9]+$", ids); mouse <- grepl("^ENSMUSG[0-9]+$", ids)
  if (organism == "auto") {
    organism <- if (all(human)) "human" else if (all(mouse)) "mouse" else "auto"
  }
  status$organism <- organism
  if (!organism %in% c("human", "mouse")) {
    status$status <- "NEEDS_ORGANISM"
    status$message <- "Select human or mouse for symbol/Entrez identifiers. Other species need a supported annotation database."
    return(finish())
  }
  if ((organism == "human" && any(mouse)) || (organism == "mouse" && any(human))) {
    status$status <- "ID_SPECIES_MISMATCH"; status$message <- "Ensembl gene IDs conflict with the selected organism; enrichment was blocked."
    return(finish())
  }
  pkg <- if (organism == "human") "org.Hs.eg.db" else "org.Mm.eg.db"
  if (!all(vapply(c("AnnotationDbi", "GO.db", pkg), requireNamespace, logical(1), quietly = TRUE))) {
    status$status <- "UNAVAILABLE"; status$message <- "Local GO annotation packages are missing."
    return(finish())
  }
  db <- get(pkg, envir = asNamespace(pkg))
  keytype <- if (all(human | mouse)) "ENSEMBL" else if (all(grepl("^[0-9]+$", ids))) "ENTREZID" else "SYMBOL"
  status$gene_id_type <- keytype
  eligible <- !is.na(res_df$padj)
  valid <- intersect(unique(ids), AnnotationDbi::keys(db, keytype = keytype))
  mapping <- if (length(valid)) AnnotationDbi::select(db, keys = valid, keytype = keytype, columns = "ENTREZID") else data.frame()
  by_id <- if (nrow(mapping)) split(mapping$ENTREZID, mapping[[keytype]]) else list()
  by_id <- lapply(by_id, function(x) unique(x[!is.na(x)]))
  clean <- by_id[lengths(by_id) == 1L]
  mapped <- unname(vapply(clean, function(x) x[[1]], character(1))[ids])
  # Multiple input rows resolving to one Entrez ID are collapsed, never counted twice.
  audit <- data.frame(gene = res_df$gene, lookup_id = ids, entrez_id = mapped,
    de_eligible = eligible, direction = res_df$direction,
    mapping_status = ifelse(ids %in% names(clean), "unique", ifelse(ids %in% names(by_id), "ambiguous", "unmapped")))
  universe <- unique(mapped[eligible & !is.na(mapped)])
  annotation <- if (length(universe)) AnnotationDbi::select(db, keys = universe, keytype = "ENTREZID", columns = "GOALL") else data.frame()
  if (nrow(annotation)) annotation <- unique(annotation[!is.na(annotation$GOALL), c("ENTREZID", "GOALL")])
  term_genes <- if (nrow(annotation)) split(annotation$ENTREZID, annotation$GOALL) else list()
  universe <- if (nrow(annotation)) intersect(universe, annotation$ENTREZID) else character()
  audit$in_background <- !is.na(mapped) & mapped %in% universe & eligible
  write.table(audit, file.path(outdir, "go_gene_mapping.tsv"), sep = "\t", quote = FALSE, row.names = FALSE, na = "")
  write.table(data.frame(entrez_id = sort(universe)), file.path(outdir, "go_background.tsv"), sep = "\t", quote = FALSE, row.names = FALSE)
  status$genes_eligible <- sum(eligible); status$genes_uniquely_mapped <- sum(eligible & !is.na(mapped))
  status$genes_unmapped <- sum(eligible & audit$mapping_status == "unmapped")
  status$genes_ambiguous <- sum(eligible & audit$mapping_status == "ambiguous")
  status$background_genes <- length(universe)
  status$annotation_versions <- list(orgDb = as.character(packageVersion(pkg)), GO_db = as.character(packageVersion("GO.db")))
  write(jsonlite::toJSON(list(organism = AnnotationDbi::metadata(db), GO = AnnotationDbi::metadata(GO.db::GO.db)),
    pretty = TRUE), file.path(outdir, "go_annotation_metadata.json"))
  term_genes <- term_genes[intersect(names(term_genes), AnnotationDbi::keys(GO.db::GO.db, keytype = "GOID"))]
  terms <- if (length(term_genes)) AnnotationDbi::select(GO.db::GO.db, keys = names(term_genes), keytype = "GOID", columns = c("TERM", "ONTOLOGY")) else data.frame()
  sets <- list(UP = mapped[res_df$direction == "UP" & eligible], DOWN = mapped[res_df$direction == "DOWN" & eligible])
  result <- go_ora(sets, universe, term_genes, terms, alpha)
  write.table(result, file.path(outdir, "go_enrichment_all.tsv"), sep = "\t", quote = FALSE, row.names = FALSE, na = "")
  significant <- result[result$significant, , drop = FALSE]
  write.table(significant, file.path(outdir, "go_enrichment_significant.tsv"), sep = "\t", quote = FALSE, row.names = FALSE, na = "")
  status$terms_tested <- nrow(result); status$significant_terms <- nrow(significant)
  status$status <- if (!length(universe)) "NO_MAPPED_BACKGROUND" else if (!nrow(result)) "NO_TESTABLE_TERMS" else if (!nrow(significant)) "NO_SIGNIFICANT_TERMS" else "SUCCEEDED"
  status$message <- switch(status$status, SUCCEEDED = "Significant GO terms found; inspect mapping coverage and sample QC before interpretation.",
    NO_SIGNIFICANT_TERMS = "No GO terms passed BH correction at the declared threshold.",
    NO_TESTABLE_TERMS = "No mapped DEG sets or GO terms met the 10–500 background-gene size limits.",
    NO_MAPPED_BACKGROUND = "No eligible genes could form a GO-annotated background.")
  if (nrow(significant)) {
    top <- head(significant, 20L)
    top$label <- make.unique(paste(top$direction, top$go_id, top$term, sep = " · "))
    top$label <- factor(top$label, levels = rev(top$label))
    plot <- ggplot2::ggplot(top, ggplot2::aes(x = -log10(pmax(padj, .Machine$double.xmin)), y = label, size = overlap, colour = direction)) +
      ggplot2::geom_point() + ggplot2::labs(title = "GO enrichment: top significant terms", x = "-log10 BH adjusted p-value", y = NULL) + ggplot2::theme_minimal(base_size = 10)
    plot_fun("go_enrichment", 12, 8, function() print(plot))
  }
  finish()
}
