#!/usr/bin/env sh
set -eu

# The Fig2_yield_seedweight_seedsize workflow alone, as its workflow.cwl runs it. Its tables go first, so the
# verify sees only what it writes.
find runs/Fig2_yield_seedweight_seedsize -type f \( -name '*.tsv' -o -name '*.txt' \) -delete
Rscript workflows/Fig2_yield_seedweight_seedsize/Fig2_yield_seedweight_seedsize.R
