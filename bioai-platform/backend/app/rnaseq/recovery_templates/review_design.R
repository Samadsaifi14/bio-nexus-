# Shared design validation for the standalone recovery scripts.
review_design <- function(metadata_path, columns, reference, test, covariates = "") {
  meta <- read.delim(metadata_path, check.names = FALSE, stringsAsFactors = FALSE, colClasses = "character")
  required <- c("sample", "condition", "experimental_unit")
  if (!all(required %in% names(meta))) stop("Metadata requires sample, condition and experimental_unit columns")
  if (anyNA(meta[, required]) || any(!nzchar(trimws(unlist(meta[, required]))))) stop("Complete the metadata; sample groups and biological units cannot be guessed")
  if (anyDuplicated(meta$sample) || anyDuplicated(meta$experimental_unit)) stop("This recovery script requires distinct samples and independent biological units; repeated measures need a reviewed model")
  if (anyDuplicated(columns) || !setequal(meta$sample, columns)) stop("Matrix/quantification names must exactly match metadata sample names; use only the selected comparison cohort")
  if (reference == test || !setequal(unique(meta$condition), c(reference, test))) stop("Declare exactly two distinct groups")
  meta <- meta[match(columns, meta$sample), , drop = FALSE]
  meta$condition <- factor(meta$condition, levels = c(reference, test))
  if (any(table(meta$condition) < 2)) stop("At least two independent samples per group are required")
  covs <- if (nzchar(covariates)) trimws(strsplit(covariates, ",", fixed = TRUE)[[1]]) else character()
  if (any(!grepl("^[A-Za-z][A-Za-z0-9_]*$", covs)) || !all(covs %in% names(meta)) || any(covs %in% required)) stop("Covariates must be additional valid metadata column names")
  technical <- names(meta)[grepl("(^|[ _-])(batch|run|lane|plate|operator|site|flowcell)([ _-]|$)", names(meta), ignore.case = TRUE)]
  varying <- technical[vapply(meta[technical], function(x) length(unique(x)) > 1, logical(1))]
  if (length(setdiff(varying, covs))) stop("Recorded varying technical variables must be included as covariates or reviewed in a separate design")
  for (key in covs) {
    if (anyNA(meta[[key]]) || any(!nzchar(trimws(meta[[key]])))) stop("Covariates cannot contain missing values")
    meta[[key]] <- factor(meta[[key]])
    if (nlevels(meta[[key]]) < 2) stop("Remove constant covariates")
  }
  formula <- reformulate(c(covs, "condition"))
  design <- model.matrix(formula, meta)
  if (qr(design)$rank != ncol(design) || nrow(design) - ncol(design) < 2) stop("Design is confounded or has insufficient residual degrees of freedom")
  rownames(meta) <- meta$sample
  list(meta = meta, formula = formula, matrix = design, coefficient = ncol(design))
}

write_provenance <- function(outdir, method, paths, notes) {
  writeLines(c(paste("Method:", method), notes, "Input checksums (MD5):", capture.output(tools::md5sum(paths)), "R/package versions:", capture.output(sessionInfo())), file.path(outdir, "provenance.txt"))
}
