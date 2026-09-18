suppressPackageStartupMessages({
  library(DESeq2)
  library(ComplexHeatmap)
  library(ggplot2)
  library(jsonlite)
  library(grid)
  library(circlize)
})

args <- commandArgs(trailingOnly = TRUE)
if (length(args) != 11) {
  stop("Expected 11 arguments: counts metadata outdir condition reference test covariates alpha lfc min_count min_samples:top_heatmap_genes")
}

counts_path <- args[[1]]
metadata_path <- args[[2]]
outdir <- args[[3]]
condition_col <- args[[4]]
reference_level <- args[[5]]
test_level <- args[[6]]
covariates_raw <- args[[7]]
alpha <- as.numeric(args[[8]])
lfc_threshold <- as.numeric(args[[9]])
min_count <- as.integer(args[[10]])
min_samples_top <- strsplit(args[[11]], ":", fixed = TRUE)[[1]]
min_samples <- as.integer(min_samples_top[[1]])
top_heatmap_genes <- as.integer(min_samples_top[[2]])

if (length(min_samples_top) != 2) stop("min_samples:top_heatmap_genes must contain two integers")
if (is.na(alpha) || alpha <= 0 || alpha >= 1) stop("alpha must be between 0 and 1")
if (is.na(lfc_threshold) || lfc_threshold < 0) stop("lfc threshold must be >= 0")
if (is.na(min_count) || min_count < 0) stop("min_count must be >= 0")
if (is.na(min_samples) || min_samples < 0) stop("min_samples must be >= 0 (use 0 for automatic smallest-group filtering)")
if (is.na(top_heatmap_genes) || top_heatmap_genes < 2) stop("top_heatmap_genes must be >= 2")

dir.create(outdir, recursive = TRUE, showWarnings = FALSE)

safe_name <- function(x) grepl("^[A-Za-z][A-Za-z0-9_.]*$", x)
if (!safe_name(condition_col)) stop("condition column has unsupported characters")

covariates <- character(0)
if (nzchar(covariates_raw)) {
  covariates <- trimws(strsplit(covariates_raw, ",", fixed = TRUE)[[1]])
  covariates <- covariates[nzchar(covariates)]
  if (any(!vapply(covariates, safe_name, logical(1)))) stop("covariate name has unsupported characters")
}

raw <- read.delim(counts_path, check.names = FALSE, stringsAsFactors = FALSE)
if (ncol(raw) < 3) stop("count matrix must contain one gene column and at least two samples")
if (anyDuplicated(raw[[1]]) > 0) stop("count matrix contains duplicate gene identifiers")
gene_ids <- as.character(raw[[1]])
counts <- as.matrix(raw[, -1, drop = FALSE])
mode(counts) <- "numeric"
rownames(counts) <- gene_ids
if (any(!is.finite(counts))) stop("count matrix contains non-finite values")
if (any(counts < 0)) stop("count matrix contains negative values")
if (any(abs(counts - round(counts)) > 1e-8)) stop("DESeq2 requires raw integer counts; non-integer values were detected")
storage.mode(counts) <- "integer"
if (anyDuplicated(colnames(counts)) > 0) stop("count matrix contains duplicate sample names")

meta <- read.delim(metadata_path, check.names = FALSE, stringsAsFactors = FALSE)
if (!("sample" %in% names(meta))) stop("metadata must contain a 'sample' column")
if (!(condition_col %in% names(meta))) stop(paste0("metadata is missing condition column '", condition_col, "'"))
if (anyDuplicated(meta$sample) > 0) stop("metadata contains duplicate sample names")
if (!setequal(meta$sample, colnames(counts))) stop("metadata sample IDs do not match count-matrix columns")
meta <- meta[match(colnames(counts), meta$sample), , drop = FALSE]
if (!identical(as.character(meta$sample), colnames(counts))) stop("metadata order could not be aligned to count columns")
rownames(meta) <- meta$sample
meta$sample <- NULL

if (!(reference_level %in% meta[[condition_col]])) stop("reference level is absent from metadata")
if (!(test_level %in% meta[[condition_col]])) stop("test level is absent from metadata")
if (identical(reference_level, test_level)) stop("reference and test levels must differ")
meta[[condition_col]] <- factor(meta[[condition_col]], levels = unique(c(reference_level, test_level, setdiff(unique(meta[[condition_col]]), c(reference_level, test_level)))))

for (term in covariates) {
  if (!(term %in% names(meta))) stop(paste0("metadata is missing covariate '", term, "'"))
  if (is.character(meta[[term]])) meta[[term]] <- factor(meta[[term]])
}

# -------------------------------------------------------------------------
# Experimental-design audit: run BEFORE DESeq2 so invalid designs fail closed
# rather than producing a plausible-looking table from unidentifiable effects.
# -------------------------------------------------------------------------
comparison_levels <- c(reference_level, test_level)
comparison_rows <- meta[[condition_col]] %in% comparison_levels
comparison_counts <- table(droplevels(meta[[condition_col]][comparison_rows]))
if (any(comparison_counts < 2)) {
  stop("each compared condition requires at least two sample rows; biological replication cannot be replaced by sequencing depth or technical repeats")
}

min_samples_requested <- min_samples
if (min_samples == 0) {
  min_samples <- as.integer(min(comparison_counts))
}

design_warnings <- character(0)
if (any(comparison_counts < 6)) {
  design_warnings <- c(
    design_warnings,
    "One or more compared groups has fewer than 6 sample rows. This is a power warning, not a universal invalidity rule; justify biological replication for the organism, variability, effect size and study design."
  )
}

experimental_unit_candidates <- c("experimental_unit", "biological_unit", "subject_id", "subject")
experimental_unit_col <- experimental_unit_candidates[experimental_unit_candidates %in% names(meta)]
experimental_unit_status <- "NOT_DECLARED"
if (length(experimental_unit_col) > 0) {
  experimental_unit_col <- experimental_unit_col[[1]]
  units <- as.character(meta[[experimental_unit_col]])
  repeated_units <- unique(units[duplicated(units) & !is.na(units) & nzchar(units)])
  if (length(repeated_units) > 0 && !(experimental_unit_col %in% covariates)) {
    stop(paste0(
      "metadata column '", experimental_unit_col,
      "' contains repeated experimental units but is absent from the model. ",
      "Technical/repeated measurements must not be treated as independent biological replicates; ",
      "declare the unit/block in the design when scientifically appropriate."
    ))
  }
  experimental_unit_status <- if (length(repeated_units) > 0) "REPEATED_AND_MODELLED" else "UNIQUE"
}

technical_pattern <- "(^|_)(batch|run|lane|plate|operator|site|processing_day|extraction_batch|kit_lot|flowcell|flow_cell)($|_)"
technical_covariates_detected <- names(meta)[grepl(technical_pattern, tolower(names(meta)), perl = TRUE)]
technical_covariates_in_model <- intersect(technical_covariates_detected, covariates)

is_nested_in_condition <- function(term) {
  technical <- as.character(meta[[term]])
  condition <- as.character(meta[[condition_col]])
  keep_rows <- !is.na(technical) & nzchar(technical) & !is.na(condition) & nzchar(condition)
  if (sum(keep_rows) < 2 || length(unique(technical[keep_rows])) < 2) return(FALSE)
  conditions_per_technical_level <- tapply(condition[keep_rows], technical[keep_rows], function(x) length(unique(x)))
  all(conditions_per_technical_level == 1)
}

confounded_columns <- technical_covariates_detected[vapply(technical_covariates_detected, is_nested_in_condition, logical(1))]
if (length(confounded_columns) > 0) {
  stop(paste0(
    "condition is confounded with recorded technical variable(s): ",
    paste(confounded_columns, collapse = ", "),
    ". Every observed level of the technical variable occurs in only one condition, so the biological and technical effects cannot be separated."
  ))
}
not_modelled <- setdiff(technical_covariates_detected, covariates)
if (length(not_modelled) > 0) {
  design_warnings <- c(
    design_warnings,
    paste0(
      "Recorded technical variable(s) not included in the statistical model: ",
      paste(not_modelled, collapse = ", "),
      ". Review PCA and study design before deciding whether adjustment is required."
    )
  )
}

design_terms <- unique(c(covariates, condition_col))
design_formula <- as.formula(paste("~", paste(design_terms, collapse = " + ")))
design_matrix <- model.matrix(design_formula, data = meta)
design_rank <- qr(design_matrix)$rank
design_columns <- ncol(design_matrix)
if (design_rank < design_columns) {
  stop(paste0(
    "design matrix is not full rank (rank ", design_rank, " of ", design_columns,
    "). The requested condition/covariates are linearly dependent or confounded, so DESeq2 cannot identify the requested effect."
  ))
}

library_sizes <- colSums(counts)
if (any(library_sizes <= 0)) stop("one or more samples has zero total library size")
library_size_fold_range <- max(library_sizes) / min(library_sizes)
library_size_df <- data.frame(
  sample = names(library_sizes),
  total_counts = as.numeric(library_sizes),
  condition = as.character(meta[names(library_sizes), condition_col]),
  row.names = NULL
)
write.table(library_size_df, file.path(outdir, "library_sizes.tsv"), sep = "\t", quote = FALSE, row.names = FALSE)

replicate_counts <- setNames(as.list(as.integer(comparison_counts)), names(comparison_counts))
design_audit <- list(
  status = "PASS_WITH_WARNINGS",
  comparison = paste0(test_level, " vs ", reference_level),
  replicate_counts = replicate_counts,
  biological_replication_note = "Sample-row counts are reported here; independence must follow the declared experimental unit. Technical repeats are not biological replicates.",
  experimental_unit_column = if (length(experimental_unit_col) > 0) experimental_unit_col else NULL,
  experimental_unit_status = experimental_unit_status,
  covariates = covariates,
  technical_covariates_detected = technical_covariates_detected,
  technical_covariates_in_model = technical_covariates_in_model,
  confounded_columns = confounded_columns,
  design = paste(deparse(design_formula), collapse = ""),
  design_rank = design_rank,
  design_columns = design_columns,
  design_full_rank = design_rank == design_columns,
  min_samples_requested = min_samples_requested,
  min_samples_effective = min_samples,
  library_size_min = min(library_sizes),
  library_size_max = max(library_sizes),
  library_size_fold_range = library_size_fold_range,
  warnings = design_warnings
)
if (length(design_warnings) == 0) design_audit$status <- "PASS"
write(toJSON(design_audit, auto_unbox = TRUE, pretty = TRUE, null = "null", digits = 10), file.path(outdir, "design_audit.json"))

dds <- DESeqDataSetFromMatrix(countData = counts, colData = meta, design = design_formula)
genes_input <- nrow(dds)
keep <- rowSums(counts(dds) >= min_count) >= min_samples
dds <- dds[keep, ]
genes_kept <- nrow(dds)
if (genes_kept < 2) stop("pre-filtering retained fewer than two genes")

dds <- estimateSizeFactors(dds)
normalized <- counts(dds, normalized = TRUE)
size_factors <- sizeFactors(dds)
size_factor_library_correlation <- suppressWarnings(cor(
  as.numeric(size_factors),
  as.numeric(library_sizes[names(size_factors)]),
  method = "pearson"
))
if (!is.finite(size_factor_library_correlation)) size_factor_library_correlation <- NA_real_

size_factor_df <- data.frame(sample = names(size_factors), size_factor = as.numeric(size_factors), row.names = NULL)
write.table(size_factor_df, file.path(outdir, "size_factors.tsv"), sep = "\t", quote = FALSE, row.names = FALSE)
write.table(data.frame(gene = rownames(normalized), normalized, check.names = FALSE), file.path(outdir, "normalized_counts.tsv"), sep = "\t", quote = FALSE, row.names = FALSE)

# vst() is fast for ordinary whole-transcriptome matrices but requires enough rows
# for its trend subsampling. varianceStabilizingTransformation() is the exact
# DESeq2 transform and is robust for small deterministic validation subsets.
vsd <- if (nrow(dds) >= 1000) {
  vst(dds, blind = TRUE)
} else {
  varianceStabilizingTransformation(dds, blind = TRUE)
}
pca <- plotPCA(vsd, intgroup = condition_col, returnData = TRUE)
percent_var <- round(100 * attr(pca, "percentVar"), 3)
pca_out <- data.frame(sample = rownames(pca), pca, row.names = NULL, check.names = FALSE)
write.table(pca_out, file.path(outdir, "pca_coordinates.tsv"), sep = "\t", quote = FALSE, row.names = FALSE)

sample_dists <- as.matrix(dist(t(assay(vsd))))
write.table(data.frame(sample = rownames(sample_dists), sample_dists, check.names = FALSE), file.path(outdir, "sample_distance_matrix.tsv"), sep = "\t", quote = FALSE, row.names = FALSE)

dds <- DESeq(dds)
res <- results(dds, contrast = c(condition_col, test_level, reference_level), alpha = alpha)
res_df <- as.data.frame(res)
res_df$gene <- rownames(res_df)
res_df <- res_df[, c("gene", setdiff(names(res_df), "gene")), drop = FALSE]
res_df <- res_df[order(res_df$padj, na.last = TRUE), , drop = FALSE]

shrink_status <- "normal"
shrunk_df <- NULL
shrunk <- tryCatch(
  lfcShrink(dds, contrast = c(condition_col, test_level, reference_level), res = res, type = "normal"),
  error = function(e) {
    shrink_status <<- paste0("unavailable: ", conditionMessage(e))
    NULL
  }
)
if (!is.null(shrunk)) {
  shrunk_df <- as.data.frame(shrunk)
  shrunk_df$gene <- rownames(shrunk_df)
  shrink_map <- setNames(shrunk_df$log2FoldChange, shrunk_df$gene)
  res_df$log2FoldChange_shrunk <- unname(shrink_map[res_df$gene])
} else {
  res_df$log2FoldChange_shrunk <- NA_real_
}

sig <- !is.na(res_df$padj) & res_df$padj < alpha & abs(res_df$log2FoldChange) > lfc_threshold
res_df$significant <- sig
res_df$direction <- ifelse(sig & res_df$log2FoldChange > 0, "UP", ifelse(sig & res_df$log2FoldChange < 0, "DOWN", "NS"))
deg_df <- res_df[sig, , drop = FALSE]
write.table(res_df, file.path(outdir, "deseq2_all_results.tsv"), sep = "\t", quote = FALSE, row.names = FALSE, na = "")
write.table(deg_df, file.path(outdir, "deseq2_significant.tsv"), sep = "\t", quote = FALSE, row.names = FALSE, na = "")

plot_svg_pdf_png <- function(name, width, height, draw_fun) {
  svg(file.path(outdir, paste0(name, ".svg")), width = width, height = height, onefile = TRUE)
  draw_fun(); dev.off()
  pdf(file.path(outdir, paste0(name, ".pdf")), width = width, height = height, onefile = TRUE)
  draw_fun(); dev.off()
  png(file.path(outdir, paste0(name, ".png")), width = width, height = height, units = "in", res = 300)
  draw_fun(); dev.off()
}

pca$.condition <- pca[[condition_col]]
pca_plot <- ggplot(pca, aes(x = PC1, y = PC2, label = name, shape = .condition)) +
  geom_point(size = 3.2) +
  geom_text(nudge_y = 0.35, check_overlap = TRUE, size = 2.7) +
  labs(title = "RNA-seq PCA on variance-stabilized counts", subtitle = paste0("PC1: ", percent_var[[1]], "% · PC2: ", percent_var[[2]], "%"), shape = condition_col) +
  theme_minimal(base_size = 11) + theme(legend.position = "bottom")
plot_svg_pdf_png("pca", 8, 6, function() print(pca_plot))

sample_ann <- data.frame(condition = as.character(meta[[condition_col]]), row.names = rownames(meta))
condition_levels <- levels(meta[[condition_col]])
condition_palette <- c("#2F6B75", "#B35C44", "#75644C", "#5B6573", "#7B627A", "#486B5A")
if (length(condition_levels) > length(condition_palette)) {
  condition_palette <- grDevices::hcl.colors(length(condition_levels), palette = "Dark 3")
}
condition_colors <- setNames(condition_palette[seq_along(condition_levels)], condition_levels)
condition_colormap <- list(condition = condition_colors)
ha <- HeatmapAnnotation(condition = sample_ann$condition, col = condition_colormap)
ra <- rowAnnotation(condition = sample_ann$condition, col = condition_colormap, show_legend = FALSE)
sd_col <- colorRamp2(c(min(sample_dists), median(sample_dists), max(sample_dists)), c("#F8FAFC", "#94A3B8", "#0F172A"))
plot_svg_pdf_png("sample_distance_heatmap", 8, 7, function() draw(Heatmap(sample_dists, name = "distance", col = sd_col, top_annotation = ha, left_annotation = ra, cluster_rows = TRUE, cluster_columns = TRUE, column_title = "Sample-to-sample distance (VST)", row_names_gp = gpar(fontsize = 7), column_names_gp = gpar(fontsize = 7))))

plot_svg_pdf_png("ma_plot", 8, 6, function() {
  plotMA(res, alpha = alpha, main = paste0(test_level, " vs ", reference_level, " · DESeq2 MA"))
  abline(h = c(-lfc_threshold, lfc_threshold), lty = 3)
})

volcano_df <- res_df[!is.na(res_df$padj) & !is.na(res_df$pvalue) & is.finite(res_df$log2FoldChange), , drop = FALSE]
volcano_df$minus_log10_padj <- -log10(pmax(volcano_df$padj, .Machine$double.xmin))
volcano_df$category <- factor(volcano_df$direction, levels = c("DOWN", "NS", "UP"))
volcano_plot <- ggplot(volcano_df, aes(x = log2FoldChange, y = minus_log10_padj, shape = category)) +
  geom_point(alpha = 0.55, size = 1.5) +
  geom_vline(xintercept = c(-lfc_threshold, lfc_threshold), linetype = 3) +
  geom_hline(yintercept = -log10(alpha), linetype = 3) +
  labs(title = paste0("DESeq2 volcano: ", test_level, " vs ", reference_level), x = "log2 fold change", y = "-log10 adjusted p-value", shape = "Call") +
  theme_minimal(base_size = 11) + theme(legend.position = "bottom")
plot_svg_pdf_png("volcano", 8, 6, function() print(volcano_plot))

heatmap_written <- FALSE
heatmap_basis <- "none"
heatmap_gene_count <- 0L
vst_matrix <- assay(vsd)
gene_variance <- apply(vst_matrix, 1, var)

if (nrow(deg_df) >= 2) {
  ordered <- deg_df[order(deg_df$padj, -abs(deg_df$log2FoldChange), na.last = TRUE), , drop = FALSE]
  selected_genes <- head(ordered$gene, top_heatmap_genes)
  heatmap_basis <- "significant_DE_genes"
} else {
  variance_order <- names(sort(gene_variance, decreasing = TRUE, na.last = NA))
  selected_genes <- head(variance_order, min(top_heatmap_genes, length(variance_order)))
  heatmap_basis <- "top_variable_genes_QC"
}

if (length(selected_genes) >= 2) {
  hm <- vst_matrix[selected_genes, , drop = FALSE]
  hm_z <- t(scale(t(hm)))
  hm_z[!is.finite(hm_z)] <- 0
  heatmap_gene_count <- nrow(hm_z)
  write.table(data.frame(gene = rownames(hm_z), hm_z, check.names = FALSE), file.path(outdir, "heatmap_matrix_zscore.tsv"), sep = "\t", quote = FALSE, row.names = FALSE)
  result_index <- match(selected_genes, res_df$gene)
  selection_df <- data.frame(
    gene = selected_genes,
    selection_basis = rep(heatmap_basis, length(selected_genes)),
    rank = seq_along(selected_genes),
    vst_variance = as.numeric(gene_variance[selected_genes]),
    padj = res_df$padj[result_index],
    log2FoldChange = res_df$log2FoldChange[result_index],
    row.names = NULL
  )
  write.table(selection_df, file.path(outdir, "heatmap_gene_selection.tsv"), sep = "\t", quote = FALSE, row.names = FALSE, na = "")
  expr_col <- colorRamp2(c(-2, 0, 2), c("#1E3A5F", "#F8FAFC", "#9A3412"))
  heatmap_title <- if (heatmap_basis == "significant_DE_genes") {
    paste0("Top ", nrow(hm_z), " significant DE genes by adjusted p-value")
  } else {
    paste0("Top ", nrow(hm_z), " variable genes (VST QC; not DEG calls)")
  }
  plot_svg_pdf_png("expression_heatmap", 9, max(6, min(12, 4 + nrow(hm_z) * 0.12)), function() draw(Heatmap(hm_z, name = "row z-score", col = expr_col, top_annotation = ha, cluster_rows = TRUE, cluster_columns = TRUE, column_title = heatmap_title, row_names_gp = gpar(fontsize = 7), column_names_gp = gpar(fontsize = 7))))
  heatmap_written <- TRUE
}

summary <- list(
  genes_input = genes_input,
  genes_kept = genes_kept,
  genes_removed = genes_input - genes_kept,
  samples = ncol(dds),
  reference_level = reference_level,
  test_level = test_level,
  condition_column = condition_col,
  covariates = covariates,
  design = paste(deparse(design_formula), collapse = ""),
  min_count = min_count,
  min_samples_requested = min_samples_requested,
  min_samples = min_samples,
  replicate_counts = replicate_counts,
  design_full_rank = design_rank == design_columns,
  design_rank = design_rank,
  design_columns = design_columns,
  design_warnings = design_warnings,
  experimental_unit_status = experimental_unit_status,
  technical_covariates_detected = technical_covariates_detected,
  technical_covariates_in_model = technical_covariates_in_model,
  library_size_min = min(library_sizes),
  library_size_max = max(library_sizes),
  library_size_fold_range = library_size_fold_range,
  size_factor_library_correlation = size_factor_library_correlation,
  alpha = alpha,
  lfc_threshold = lfc_threshold,
  significant = nrow(deg_df),
  up = sum(deg_df$log2FoldChange > 0),
  down = sum(deg_df$log2FoldChange < 0),
  pca_percent_variance = list(PC1 = percent_var[[1]], PC2 = percent_var[[2]]),
  size_factor_min = min(size_factors),
  size_factor_max = max(size_factors),
  lfc_shrinkage = shrink_status,
  expression_heatmap_generated = heatmap_written,
  expression_heatmap_basis = heatmap_basis,
  expression_heatmap_genes = heatmap_gene_count,
  package_versions = list(
    R = R.version.string,
    DESeq2 = as.character(packageVersion("DESeq2")),
    ComplexHeatmap = as.character(packageVersion("ComplexHeatmap")),
    ggplot2 = as.character(packageVersion("ggplot2")),
    circlize = as.character(packageVersion("circlize"))
  )
)
write(toJSON(summary, auto_unbox = TRUE, pretty = TRUE, null = "null", digits = 10), file.path(outdir, "analysis_summary.json"))
