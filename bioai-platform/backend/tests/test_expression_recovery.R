# Execute the shipped recovery scripts and compare against direct package results.
suppressPackageStartupMessages({library(limma); library(tximport); library(DESeq2)})
folder <- tempfile("recovery-test-"); dir.create(folder)
templates <- normalizePath("app/rnaseq/recovery_templates")
set.seed(819)
samples <- paste0("s", 1:6)
meta <- data.frame(sample = samples, condition = rep(c("control", "test"), each = 3), experimental_unit = samples)
metadata <- file.path(folder, "metadata.tsv")
write.table(meta, metadata, sep = "\t", quote = FALSE, row.names = FALSE)
expression <- matrix(exp(rnorm(1200, mean = 3, sd = 0.4)), nrow = 200, dimnames = list(paste0("g", 1:200), samples))
expression[1:20, 4:6] <- expression[1:20, 4:6] * 3
path <- file.path(folder, "expression.tsv")
write.table(data.frame(gene = rownames(expression), expression), path, sep = "\t", quote = FALSE, row.names = FALSE)
out <- file.path(folder, "limma")
status <- system2(file.path(R.home("bin"), "Rscript"), c(file.path(templates, "limma_trend.R"), path, metadata, "control", "test", "FPKM", out))
stopifnot(status == 0)
observed <- read.delim(file.path(out, "limma_trend_results.tsv"))
expected <- topTable(eBayes(lmFit(log2(expression + 1), model.matrix(~factor(meta$condition, levels = c("control", "test")))), trend = TRUE), coef = 2, number = Inf, sort.by = "none")
stopifnot(max(abs(observed$logFC - expected$logFC)) < 1e-10, max(abs(observed$adj.P.Val - expected$adj.P.Val)) < 1e-10)
stopifnot(all(file.exists(file.path(out, paste0("volcano.", c("svg", "pdf", "png"))))))

# Genuine Salmon file shape with fractional estimated counts and sample-dependent lengths.
files <- setNames(file.path(folder, paste0(samples, ".sf")), samples)
for (i in seq_along(files)) {
  counts <- rnbinom(200, mu = if (i > 3) c(rep(350, 20), rep(100, 180)) else rep(100, 200), size = 12) + 0.25
  length <- seq(700, 1695, by = 5)
  effective <- length - 120 + i * 3
  abundance <- counts / effective
  q <- data.frame(Name = paste0("tx", 1:200), Length = length, EffectiveLength = effective, TPM = abundance / sum(abundance) * 1e6, NumReads = counts)
  write.table(q, files[i], sep = "\t", quote = FALSE, row.names = FALSE)
}
manifest <- file.path(folder, "quantfiles.tsv"); mapping <- file.path(folder, "tx2gene.tsv")
write.table(data.frame(sample = samples, quant_file = unname(files)), manifest, sep = "\t", quote = FALSE, row.names = FALSE)
tx2gene <- data.frame(transcript = paste0("tx", 1:200), gene = paste0("g", 1:200))
write.table(tx2gene, mapping, sep = "\t", quote = FALSE, row.names = FALSE)
txout <- file.path(folder, "tximport")
status <- system2(file.path(R.home("bin"), "Rscript"), c(file.path(templates, "tximport_deseq2.R"), manifest, mapping, metadata, "control", "test", txout))
stopifnot(status == 0)
observed_dds <- readRDS(file.path(txout, "dds_with_length_offsets.rds"))
txi <- tximport(files, type = "salmon", tx2gene = tx2gene)
meta$condition <- factor(meta$condition, levels = c("control", "test")); rownames(meta) <- meta$sample
expected_dds <- DESeq(DESeqDataSetFromTximport(txi, meta, ~condition))
stopifnot(isTRUE(all.equal(normalizationFactors(observed_dds), normalizationFactors(expected_dds))), isTRUE(all.equal(counts(observed_dds), counts(expected_dds))))
observed <- read.delim(file.path(txout, "deseq2_tximport_results.tsv"))
expected <- as.data.frame(results(expected_dds, contrast = c("condition", "test", "control"), alpha = 0.05))
stopifnot(isTRUE(all.equal(observed$log2FoldChange, expected$log2FoldChange)), isTRUE(all.equal(observed$padj, expected$padj)))
source(file.path(templates, "review_design.R"))
meta$experimental_unit[2] <- meta$experimental_unit[1]
write.table(meta, metadata, sep = "\t", quote = FALSE, row.names = FALSE)
stopifnot(inherits(try(review_design(metadata, samples, "control", "test"), silent = TRUE), "try-error"))
cat("Expression recovery known-answer tests passed\n")
