args <- commandArgs(trailingOnly = TRUE)
if (length(args) != 3L) stop("Expected results.tsv, options.json and output directory.")
script <- sub("^--file=", "", grep("^--file=", commandArgs(), value = TRUE)[[1]])
source(file.path(dirname(script), "go_enrichment.R"))
options <- jsonlite::fromJSON(args[[2]])
res <- read.delim(args[[1]], colClasses = c(gene = "character"), check.names = FALSE, quote = "", comment.char = "", na.strings = c("", "NA"))
out <- args[[3]]; dir.create(out, recursive = TRUE, showWarnings = FALSE)
plot_fun <- function(name, width, height, draw_fun) {
  svg(file.path(out, paste0(name, ".svg")), width = width, height = height); draw_fun(); dev.off()
  pdf(file.path(out, paste0(name, ".pdf")), width = width, height = height); draw_fun(); dev.off()
  png(file.path(out, paste0(name, ".png")), width = width, height = height, units = "in", res = 300); draw_fun(); dev.off()
}
do.call(run_go_enrichment, c(list(res_df = res, outdir = out, plot_fun = plot_fun), options))
