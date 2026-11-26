#!/usr/bin/env sh
set -eu

# The package's tables go first, so the verify sees only what this run writes: a table the analysis no longer
# produces is missing, not the authors' copy.
find output -type f \( -name '*.tex' -o -name '*.txt' \) -delete

# Every table and figure of the paper, rendered as the package's README says: the cached results of the
# hours-long bootstraps in data/precomputed/ are read, not recomputed.
Rscript run_all.R
