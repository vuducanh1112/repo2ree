#!/usr/bin/env sh
set -eu

# Every stage of the capsule from its observed data: the first stage's city-specific fits, the second stage's
# meta-analysis, the modeled suicide counts, then the projection. The capsule's code/run.sh, its Reproducible
# Run, leaves all but the projection commented out, and projects from the results of the first three stages the
# capsule holds. Each stage writes its results over the authors' copies in data/output and data/modeled, so
# those are kept aside first, and every number they hold is set beside the one this run writes, in
# results/agreement.tsv.
STAGES="data/output/1st_coef_vcov.RData data/output/mvoverall.RData data/output/mypred.RData
data/output/metavariable.RData data/output/blupres.RData data/output/New_blups.RData
data/modeled/modeled_suicide.RData data/output/ANAF.RData data/output/ANAF_city.RData"
AUTHORS=$(mktemp -d)
# shellcheck disable=SC2086
cp $STAGES "$AUTHORS/"

Rscript /code/Setting.R
# The first two stages draw on whatever device is open, which Code Ocean's RStudio gives them room on and a
# script run does not: R's default device of 7 inches has no room for the margins of their grids of plots, and
# each stage stops once it has saved its results. The first stage plots its 24 fits per page on the device its
# pdf() call, commented out, would open; the second its Figure S3, 30 countries, on none of its own, and here
# on a page of 12 by 14 inches. The devices are opened before the scripts run, unchanged.
Rscript -e 'pdf("/results/1st_stage_overall.pdf", width = 9, height = 13); source("/code/1.FirstStage.R")'
Rscript -e 'pdf("/results/FigureS3.pdf", width = 12, height = 14); source("/code/2.SecondStage.R")'
Rscript /code/3.ModeledSuicide.R
Rscript /code/4.ProjectionANAF.R

# shellcheck disable=SC2086
R --vanilla -s -f /dev/stdin --args "$AUTHORS" $STAGES <<'EOF'
# Every number each .RData holds, the regenerated copy beside the authors': how many, how many differ, and
# by how much at most. An array with an est, ci.l and ci.u slice is compared slice by slice: the estimates
# are computed, the bounds drawn by Monte Carlo. The regenerated numbers go to results/values.tsv.
args <- commandArgs(trailingOnly = TRUE)
authors <- args[1]
numbers <- function(x) {
  if (is.environment(x) || is.function(x) || is.language(x)) return(numeric())
  if (is.list(x)) return(unlist(lapply(unclass(x), numbers), use.names = FALSE))
  if (is.numeric(x) || is.logical(x) || is.complex(x)) return(as.numeric(x))
  numeric()
}
slices <- function(x) {
  axis <- if (is.array(x)) which(vapply(dimnames(x), function(d) "est" %in% d, TRUE)) else integer()
  if (length(axis) != 1) return(list(all = numbers(x)))
  lapply(asplit(x, axis), as.numeric)
}
loaded <- function(file) {
  held <- new.env()
  load(file, envir = held)
  held
}
rows <- list()
values <- file("results/values.tsv", "w")
for (file in args[-1]) {
  theirs <- loaded(file.path(authors, basename(file)))
  ours <- loaded(file)
  for (name in sort(union(ls(theirs), ls(ours)))) {
    held <- exists(name, theirs, inherits = FALSE) && exists(name, ours, inherits = FALSE)
    a <- if (held) slices(get(name, theirs)) else list()
    b <- if (held) slices(get(name, ours)) else list()
    if (!held || !identical(names(a), names(b))) {
      rows[[length(rows) + 1]] <- data.frame(file = file, object = name, slice = NA, values = NA, differing = NA,
                                             max_abs_diff = NA, max_rel_diff = NA)
      next
    }
    for (slice in names(b)) {
      x <- a[[slice]]
      y <- b[[slice]]
      writeLines(paste(file, name, slice, format(y, digits = 15), sep = "\t"), values)
      if (length(x) != length(y)) {
        rows[[length(rows) + 1]] <- data.frame(file = file, object = name, slice = slice, values = NA,
                                               differing = NA, max_abs_diff = NA, max_rel_diff = NA)
        next
      }
      apart <- is.na(x) != is.na(y)
      both <- !is.na(x) & !is.na(y)
      abs_diff <- abs(x[both] - y[both])
      rel_diff <- ifelse(abs_diff == 0, 0, abs_diff / pmax(abs(x[both]), abs(y[both])))
      rows[[length(rows) + 1]] <- data.frame(
        file = file, object = name, slice = slice, values = length(y),
        differing = sum(apart) + sum(abs_diff != 0),
        max_abs_diff = if (any(apart)) Inf else signif(max(c(0, abs_diff)), 2),
        max_rel_diff = if (any(apart)) Inf else signif(max(c(0, rel_diff)), 2)
      )
    }
  }
}
close(values)
write.table(do.call(rbind, rows), "results/agreement.tsv", sep = "\t", quote = FALSE, row.names = FALSE)
EOF
