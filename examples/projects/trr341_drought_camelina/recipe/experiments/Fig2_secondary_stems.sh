#!/usr/bin/env sh
set -eu

# The Fig2_secondary_stems workflow alone, as its workflow.cwl runs it. Its tables go first, so the verify sees
# only what it writes.
find runs/Fig2_secondary_stems -type f \( -name '*.tsv' -o -name '*.txt' \) -delete
Rscript workflows/Fig2_secondary_stems/Fig2_secondary_stems.R
