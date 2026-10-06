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

# Resolve each row independently. Official symbols take priority over aliases;
# one-to-many mappings remain unresolved rather than selecting the first match.
resolve_gene_ids <- function(ids, db, id_type = "auto", aliases = TRUE) {
  lookup <- trimws(ids)
  is_ens <- grepl("^ENS[A-Z]*[GT][0-9]+(\\.[0-9]+)?$", lookup)
  lookup[is_ens] <- sub("\\.[0-9]+$", "", lookup[is_ens])
  types <- if (id_type == "auto") ifelse(grepl("^ENS[A-Z]*G[0-9]+$", lookup), "ENSEMBL",
    ifelse(grepl("^ENS[A-Z]*T[0-9]+$", lookup), "ENSEMBLTRANS",
      ifelse(grepl("^[0-9]+$", lookup), "ENTREZID", "SYMBOL"))) else rep(id_type, length(ids))
  mapped <- rep(NA_character_, length(ids)); state <- rep("unmapped", length(ids)); route <- types
  query <- function(ix, keytype) {
    if (!length(ix) || !keytype %in% AnnotationDbi::keytypes(db)) return()
    valid <- intersect(unique(lookup[ix]), AnnotationDbi::keys(db, keytype = keytype))
    if (!length(valid)) return()
    m <- AnnotationDbi::select(db, keys = valid, keytype = keytype, columns = "ENTREZID")
    groups <- lapply(split(m$ENTREZID, m[[keytype]]), function(x) unique(x[!is.na(x)]))
    for (i in ix) {
      values <- groups[[lookup[i]]]
      if (length(values) == 1L) { mapped[i] <<- values; state[i] <<- "unique"; route[i] <<- keytype }
      if (length(values) > 1L) { state[i] <<- "ambiguous"; route[i] <<- keytype }
    }
  }
  for (type in unique(types)) query(which(types == type), type)
  if (aliases) query(which(types == "SYMBOL" & state == "unmapped"), "ALIAS")
  data.frame(gene = ids, lookup_id = lookup, entrez_id = mapped, mapping_status = state, mapping_route = route)
}

read_gene_sets <- function(path) {
  lines <- readLines(path, warn = FALSE, encoding = "UTF-8")
  lines <- lines[nzchar(trimws(lines))]
  if (!length(lines) || length(lines) > 10000L) stop("GMT must contain 1–10,000 gene sets.")
  fields <- strsplit(lines, "\t", fixed = TRUE)
  if (any(lengths(fields) < 3L)) stop("Each GMT row needs a term, description and at least one gene, separated by tabs.")
  ids <- vapply(fields, `[[`, character(1), 1L)
  if (any(!nzchar(ids)) || anyDuplicated(ids)) stop("GMT term identifiers must be non-empty and unique.")
  sets <- lapply(fields, function(x) unique(trimws(x[-c(1L, 2L)])))
  if (any(vapply(sets, function(x) any(!nzchar(x)), logical(1)))) stop("GMT contains an empty gene identifier.")
  names(sets) <- ids
  list(sets = sets, terms = data.frame(GOID = ids, TERM = vapply(fields, `[[`, character(1), 2L), ONTOLOGY = "CUSTOM"))
}

# Competitive rank-sum sensitivity analysis on signed DESeq2 Wald statistics.
# It is not GSEA and does not model inter-gene correlation or permute samples.
ranked_gene_sets <- function(scores, term_genes, terms, alpha) {
  rows <- list(); universe <- names(scores); N <- length(scores)
  ranks <- rank(scores, ties.method = "average")
  ties <- table(scores); tie_sum <- sum(ties^3 - ties)
  for (term in names(term_genes)) {
    members <- intersect(term_genes[[term]], universe); m <- length(members); n <- N - m
    if (m < 10L || m > 500L || n < 2L) next
    W <- sum(ranks[match(members, universe)]) - m * (m + 1) / 2
    sd_w <- sqrt((m * n / 12) * ((N + 1) - tie_sum / (N * (N - 1))))
    for (direction in c("UP", "DOWN")) {
      # stats::wilcox.test normal approximation and continuity correction.
      # Rank once instead of sorting the same universe for every term.
      correction <- if (direction == "UP") 0.5 else -0.5
      p <- if (sd_w == 0) 1 else pnorm((W - m * n / 2 - correction) / sd_w, lower.tail = direction == "DOWN")
      rows[[length(rows) + 1L]] <- data.frame(direction = direction, go_id = term,
        term = terms$TERM[match(term, terms$GOID)], ontology = terms$ONTOLOGY[match(term, terms$GOID)],
        term_size = length(members), universe_size = length(universe),
        median_wald_statistic = median(scores[members]), pvalue = p, genes = paste(sort(members), collapse = ";"))
    }
  }
  if (!length(rows)) return(data.frame(direction = character(), go_id = character(), term = character(), ontology = character(),
    term_size = integer(), universe_size = integer(), median_wald_statistic = numeric(), pvalue = numeric(), genes = character(),
    padj = numeric(), significant = logical()))
  result <- do.call(rbind, rows); result$padj <- p.adjust(result$pvalue, "BH"); result$significant <- result$padj < alpha
  result[order(result$padj, result$go_id, result$direction), , drop = FALSE]
}

run_go_enrichment <- function(res_df, organism, outdir, alpha, plot_fun, database = "GO", method = "ora",
    id_type = "auto", aliases = TRUE, gmt_path = "", mapping_path = "", database_label = "", namespace = "") {
  if (!database %in% c("GO", "GO:BP", "GO:MF", "GO:CC", "CUSTOM")) stop("Unsupported gene-set database.")
  if (!method %in% c("ora", "ranked_wilcoxon")) stop("Unsupported enrichment method.")
  status <- list(status = "NOT_RUN", message = "", organism = organism, database = database,
    method = if (method == "ora") "One-sided hypergeometric ORA; BH across all term-direction tests" else
      "Competitive Wilcoxon rank-sum on signed Wald statistics; asymptotic tie correction; BH across all term-direction tests",
    method_key = method, R_version = R.version.string, alias_fallback = aliases, min_term_size = 10L, max_term_size = 500L, alpha = alpha,
    background = if (method == "ora") "DESeq2 non-missing adjusted p-values; uniquely mapped, annotated genes" else
      "DESeq2 non-missing p-values and finite Wald statistics; uniquely mapped, annotated genes; duplicate targets use median statistic",
    recovery_options = c("Review organism and ID type", "Enable unique symbol-alias recovery", "Supply a species-matched GMT and optional ID mapping"))
  finish <- function() {
    write(jsonlite::toJSON(status, auto_unbox = TRUE, pretty = TRUE, null = "null"), file.path(outdir, "go_enrichment_summary.json")); status
  }
  required <- c("gene", "padj", "direction")
  if (!all(required %in% names(res_df))) stop("Saved results are missing gene, padj or direction columns.")
  if (method == "ranked_wilcoxon" && !all(c("stat", "pvalue") %in% names(res_df))) stop("This saved run has no Wald statistics for ranked testing.")
  eligible <- if (method == "ora") !is.na(res_df$padj) else !is.na(res_df$pvalue) & is.finite(res_df$stat)
  ids <- as.character(res_df$gene)
  if (database == "CUSTOM") {
    if (!nzchar(gmt_path) || !nzchar(database_label) || !nzchar(namespace) || organism %in% c("", "auto"))
      stop("Custom gene sets require GMT, source/release label, identifier namespace and declared organism.")
    custom <- read_gene_sets(gmt_path); term_genes <- custom$sets; terms <- custom$terms
    targets <- ids; states <- rep("exact", length(ids))
    if (nzchar(mapping_path)) {
      m <- read.delim(mapping_path, colClasses = "character", check.names = FALSE, quote = "", comment.char = "", na.strings = "")
      if (!all(c("source_id", "target_id") %in% names(m)) || anyNA(m[c("source_id", "target_id")])) stop("Mapping TSV requires non-empty source_id and target_id columns.")
      groups <- lapply(split(m$target_id, m$source_id), unique)
      targets <- vapply(ids, function(id) { v <- groups[[id]]; if (length(v) == 1L) v else NA_character_ }, character(1))
      states <- vapply(ids, function(id) { n <- length(groups[[id]]); if (n == 1L) "unique" else if (n > 1L) "ambiguous" else "unmapped" }, character(1))
    }
    audit <- data.frame(gene = ids, lookup_id = ids, entrez_id = targets, mapping_status = states, mapping_route = "CUSTOM")
    status$gene_id_type <- namespace; status$database_label <- database_label
    status$annotation_versions <- list(source = database_label, identifier_namespace = namespace, organism_verification = "user-declared")
  } else {
    human <- grepl("^ENSG[0-9]+(\\.[0-9]+)?$|^ENST[0-9]+(\\.[0-9]+)?$", ids)
    mouse <- grepl("^ENSMUS[GT][0-9]+(\\.[0-9]+)?$", ids)
    other_ens <- grepl("^ENS[A-Z]+[GT][0-9]+", ids) & !human & !mouse
    if (organism == "auto" && !any(other_ens)) {
      if (any(human) && !any(mouse)) organism <- "human"
      if (any(mouse) && !any(human)) organism <- "mouse"
    }
    status$organism <- organism
    if ((any(human) && any(mouse)) || (organism == "human" && any(mouse | other_ens)) || (organism == "mouse" && any(human | other_ens))) {
      status$status <- "ID_SPECIES_MISMATCH"; status$message <- "Conflicting species identifiers detected. Review the organism and mapping; no enrichment was calculated."; return(finish())
    }
    if (!organism %in% c("human", "mouse")) {
      status$status <- "NEEDS_ORGANISM"; status$message <- "Choose the documented organism. Human/mouse use local GO; other species can use a species-matched GMT. Sample groups cannot be inferred from gene identifiers."; return(finish())
    }
    pkg <- if (organism == "human") "org.Hs.eg.db" else "org.Mm.eg.db"
    if (!all(vapply(c("AnnotationDbi", "GO.db", pkg), requireNamespace, logical(1), quietly = TRUE))) {
      status$status <- "UNAVAILABLE"; status$message <- "Local annotations are unavailable. Supply a versioned GMT to run locally with exact IDs."; return(finish())
    }
    db <- get(pkg, envir = asNamespace(pkg)); audit <- resolve_gene_ids(ids, db, id_type, aliases)
    status$gene_id_type <- if (id_type == "auto") paste(sort(unique(audit$mapping_route)), collapse = "+") else id_type
    universe <- unique(audit$entrez_id[eligible & !is.na(audit$entrez_id)])
    annotation <- if (length(universe)) AnnotationDbi::select(db, keys = universe, keytype = "ENTREZID", columns = "GOALL") else data.frame()
    if (nrow(annotation)) annotation <- unique(annotation[!is.na(annotation$GOALL), c("ENTREZID", "GOALL")])
    term_genes <- if (nrow(annotation)) split(annotation$ENTREZID, annotation$GOALL) else list()
    term_genes <- term_genes[intersect(names(term_genes), AnnotationDbi::keys(GO.db::GO.db, keytype = "GOID"))]
    terms <- if (length(term_genes)) AnnotationDbi::select(GO.db::GO.db, keys = names(term_genes), keytype = "GOID", columns = c("TERM", "ONTOLOGY")) else data.frame()
    if (database != "GO" && nrow(terms)) { terms <- terms[terms$ONTOLOGY == sub("GO:", "", database), ]; term_genes <- term_genes[terms$GOID] }
    status$annotation_versions <- list(orgDb = as.character(packageVersion(pkg)), GO_db = as.character(packageVersion("GO.db")))
    write(jsonlite::toJSON(list(organism = AnnotationDbi::metadata(db), GO = AnnotationDbi::metadata(GO.db::GO.db)), pretty = TRUE), file.path(outdir, "go_annotation_metadata.json"))
  }
  mapped <- audit$entrez_id
  annotated <- unique(unlist(term_genes, use.names = FALSE))
  universe <- intersect(unique(mapped[eligible & !is.na(mapped)]), annotated)
  audit$de_eligible <- eligible; audit$direction <- res_df$direction
  audit$in_background <- eligible & !is.na(mapped) & mapped %in% universe
  # Generic target_id disambiguates custom namespaces; legacy Entrez column retained for old consumers.
  audit$target_id <- mapped
  if (database == "CUSTOM") audit$entrez_id <- NULL
  write.table(audit, file.path(outdir, "go_gene_mapping.tsv"), sep = "\t", quote = FALSE, row.names = FALSE, na = "")
  write.table(data.frame(gene_id = sort(universe)), file.path(outdir, "go_background.tsv"), sep = "\t", quote = FALSE, row.names = FALSE)
  status$genes_eligible <- sum(eligible); status$genes_uniquely_mapped <- sum(eligible & !is.na(mapped))
  status$genes_unmapped <- sum(eligible & audit$mapping_status == "unmapped"); status$genes_ambiguous <- sum(eligible & audit$mapping_status == "ambiguous")
  status$aliases_recovered <- sum(eligible & audit$mapping_route == "ALIAS" & !is.na(mapped))
  status$background_genes <- length(universe)
  status$mapping_coverage <- if (sum(eligible)) sum(eligible & !is.na(mapped)) / sum(eligible) else 0
  status$annotation_coverage <- if (sum(eligible)) sum(audit$in_background) / sum(eligible) else 0
  status$coverage_warning <- if (status$annotation_coverage < 0.5) "Fewer than half of eligible rows are in the annotated background. Review identifiers and database coverage before interpreting results." else ""
  if (database == "CUSTOM") write(jsonlite::toJSON(status$annotation_versions, pretty = TRUE), file.path(outdir, "go_annotation_metadata.json"))
  if (method == "ora") {
    sets <- list(UP = mapped[res_df$direction == "UP" & eligible], DOWN = mapped[res_df$direction == "DOWN" & eligible])
    conflicts <- intersect(intersect(sets$UP, sets$DOWN), universe)
    status$direction_conflicts <- length(conflicts)
    sets <- lapply(sets, setdiff, y = conflicts)
    result <- go_ora(sets, universe, term_genes, terms, alpha)
  } else {
    scores <- tapply(res_df$stat[audit$in_background], mapped[audit$in_background], median)
    scores <- setNames(as.numeric(scores), names(scores))
    write.table(data.frame(gene_id = names(scores), wald_statistic = scores), file.path(outdir, "go_ranked_statistics.tsv"), sep = "\t", quote = FALSE, row.names = FALSE)
    result <- ranked_gene_sets(scores, term_genes, terms, alpha)
    status$interpretation_note <- "Exploratory competitive rank-sum test, not GSEA. Gene correlation is not modeled; BH values are conditional on this test's assumptions."
  }
  write.table(result, file.path(outdir, "go_enrichment_all.tsv"), sep = "\t", quote = FALSE, row.names = FALSE, na = "")
  significant <- result[result$significant, , drop = FALSE]
  write.table(significant, file.path(outdir, "go_enrichment_significant.tsv"), sep = "\t", quote = FALSE, row.names = FALSE, na = "")
  status$terms_tested <- nrow(result); status$significant_terms <- nrow(significant)
  status$status <- if (!length(universe)) "NO_MAPPED_BACKGROUND" else if (!nrow(result)) "NO_TESTABLE_TERMS" else if (!nrow(significant)) "NO_SIGNIFICANT_TERMS" else "SUCCEEDED"
  status$message <- switch(status$status, SUCCEEDED = "Significant terms found. Review mapping coverage, database scope and sample QC before interpretation.",
    NO_SIGNIFICANT_TERMS = "No terms passed BH correction. A null result is valid; alternative methods are sensitivity analyses, not a search for significance.",
    NO_TESTABLE_TERMS = "No eligible gene sets met the 10–500 background-gene limits, or no DEGs passed the declared cutoffs. A ranked analysis is available without a DEG cutoff.",
    NO_MAPPED_BACKGROUND = "No eligible genes matched this annotation set. Review ID type, organism, aliases or supply a matching GMT and ID mapping.")
  if (nrow(significant)) {
    top <- head(significant, 20L); top$label <- make.unique(paste(top$direction, top$go_id, top$term, sep = " · "))
    top$label <- factor(top$label, levels = rev(top$label))
    top$plotted_size <- if (method == "ora") top$overlap else top$term_size
    plot <- ggplot2::ggplot(top, ggplot2::aes(x = -log10(pmax(padj, .Machine$double.xmin)), y = label, size = plotted_size, colour = direction)) +
      ggplot2::geom_point() + ggplot2::labs(title = paste(database, "enrichment ·", method), x = "-log10 BH adjusted p-value", y = NULL,
        size = if (method == "ora") "DEG overlap" else "Set size") + ggplot2::theme_minimal(base_size = 10)
    plot_fun("go_enrichment", 12, 8, function() print(plot))
  }
  finish()
}
