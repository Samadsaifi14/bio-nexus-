# Independent package-level calculation: never sources BioNexus analysis code
# or reads its fitted objects or QC checkpoint.
suppressPackageStartupMessages({library(DESeq2); library(jsonlite)})
a <- commandArgs(TRUE)
raw <- read.delim(a[1], check.names = FALSE)
m <- read.delim(a[2], row.names = 1)
m <- m[colnames(raw)[-1], , drop = FALSE]
m$condition <- factor(m$condition, levels = c("healthy", "SALS"))
c <- as.matrix(raw[, -1]); rownames(c) <- raw$gene
d <- DESeqDataSetFromMatrix(c, m, ~condition)
d <- d[rowSums(counts(d) >= 10) >= 8, ]
d <- estimateSizeFactors(d)
norm <- counts(d, normalized = TRUE)
sf <- data.frame(sample = colnames(d), size_factor = as.numeric(sizeFactors(d)))
v <- if (nrow(d) >= 1000) vst(d, blind = TRUE) else varianceStabilizingTransformation(d, blind = TRUE)
p <- plotPCA(v, intgroup = "condition", returnData = TRUE)
d <- DESeq(d)
r <- as.data.frame(results(d, contrast = c("condition", "SALS", "healthy"), alpha = .05))
r$gene <- rownames(r)
r$significant <- !is.na(r$padj) & r$padj < .05 & abs(r$log2FoldChange) > 1
r <- r[order(r$padj, na.last = TRUE), ]
write_table <- function(value, name) write.table(value, file.path(a[3], name), sep = "\t", quote = FALSE, row.names = FALSE, na = "")
dir.create(a[3], recursive = TRUE, showWarnings = FALSE)
write_table(r, "deseq2_all_results.tsv")
write_table(sf, "size_factors.tsv")
write_table(data.frame(gene = rownames(norm), norm, check.names = FALSE), "normalized_counts.tsv")
write_table(data.frame(sample = rownames(p), p, check.names = FALSE), "pca_coordinates.tsv")
distances <- as.matrix(dist(t(assay(v))))
write_table(data.frame(sample = rownames(distances), distances, check.names = FALSE), "sample_distance_matrix.tsv")
volcano <- r[!is.na(r$padj) & !is.na(r$pvalue) & is.finite(r$log2FoldChange), ]
volcano$minus_log10_padj <- -log10(pmax(volcano$padj, .Machine$double.xmin))
write_table(volcano, "volcano_plot_data.tsv")
degs <- r[r$significant, ]
variances <- apply(assay(v), 1, var)
chosen <- if (nrow(degs) >= 2) head(degs[order(degs$padj, -abs(degs$log2FoldChange)), "gene"], 40) else head(names(sort(variances, decreasing = TRUE, na.last = NA)), 40)
chosen <- chosen[is.finite(variances[chosen]) & variances[chosen] > 0]
if (length(chosen) >= 2) {
  z <- t(scale(t(assay(v)[chosen, , drop = FALSE])))
  write_table(data.frame(gene = rownames(z), z, check.names = FALSE), "heatmap_matrix_zscore.tsv")
}
capture.output(sessionInfo(), file = file.path(a[3], "sessionInfo.txt"))
