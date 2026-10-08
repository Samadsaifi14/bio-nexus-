# Exploratory continuous-expression fallback. Never passes normalized data to DESeq2/voom.
args <- commandArgs(trailingOnly = TRUE)
if (length(args) < 6 || length(args) > 7) stop("Usage: Rscript limma_trend.R expression.tsv metadata.tsv reference test FPKM|TPM outdir [covariates]")
script <- sub("^--file=", "", commandArgs()[grepl("^--file=", commandArgs())][1])
source(file.path(dirname(normalizePath(script)), "review_design.R"))
suppressPackageStartupMessages(library(limma))
if (!(args[5] %in% c("FPKM", "TPM"))) stop("Explicitly declare unlogged, nonnegative FPKM or TPM; do not double-log transformed data")
tab <- read.delim(args[1], check.names = FALSE, stringsAsFactors = FALSE)
if (ncol(tab) < 5 || anyNA(tab[[1]]) || any(!nzchar(tab[[1]])) || anyDuplicated(tab[[1]])) stop("Expression TSV requires unique feature IDs and at least four sample columns; remove annotation columns first")
if (!all(vapply(tab[-1], is.numeric, logical(1)))) stop("All columns after feature ID must be numeric sample expression; remove gene_symbol/gene_id_clean annotations")
x <- as.matrix(tab[-1]); rownames(x) <- tab[[1]]
if (any(!is.finite(x)) || any(x < 0)) stop("Expression must be finite, nonnegative and unlogged")
d <- review_design(args[2], colnames(x), args[3], args[4], if (length(args) == 7) args[7] else "")
# Outcome-independent low-expression filter, explicitly recorded below.
min_samples <- min(table(d$meta$condition))
keep <- rowSums(x >= 1) >= min_samples
if (sum(keep) < 20) stop("Fewer than 20 retained features; insufficient features for this generic trend fallback")
log_expression <- log2(x[keep, , drop = FALSE] + 1)
fit <- eBayes(lmFit(log_expression, d$matrix), trend = TRUE)
res <- topTable(fit, coef = d$coefficient, number = Inf, adjust.method = "BH", sort.by = "none")
out <- args[6]; dir.create(out, recursive = TRUE, showWarnings = FALSE)
write.table(data.frame(feature = rownames(res), res, row.names = NULL), file.path(out, "limma_trend_results.tsv"), sep = "\t", quote = FALSE, row.names = FALSE)
write.table(data.frame(feature = rownames(log_expression), log_expression, check.names = FALSE), file.path(out, "log_expression.tsv"), sep = "\t", quote = FALSE, row.names = FALSE)
write.table(d$matrix, file.path(out, "design_matrix.tsv"), sep = "\t", quote = FALSE)
for (format in c("svg", "pdf", "png")) {
  path <- file.path(out, paste0("volcano.", format))
  if (format == "svg") svg(path) else if (format == "pdf") pdf(path) else png(path, width = 1600, height = 1200, res = 160)
  plot(res$logFC, -log10(pmax(res$adj.P.Val, .Machine$double.xmin)), xlab = "Difference in log2(expression + 1)", ylab = "-log10 BH adjusted p-value", main = "Exploratory limma-trend on normalized expression", pch = 16)
  dev.off()
}
write_provenance(out, "limma-trend (exploratory normalized-expression fallback)", args[1:2], c(paste("Source units:", args[5]), "Transformation: log2(expression + 1); no further between-sample normalization", paste("Filter: expression >= 1 in at least", min_samples, "samples"), paste("Contrast:", args[4], "minus", args[3]), paste("Design:", deparse(d$formula)), "Effects are differences on the transformed scale, not DESeq2 count-model log fold changes.", "Original library-size/composition information is unavailable. Review normalization, mean-variance fit and low-expression sensitivity before interpretation. Results are exploratory, not a count-based replacement."))
