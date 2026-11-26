#!/usr/bin/env sh
set -eu

# The Fig5_germination workflow alone, as its workflow.cwl runs it. Its tables go first, so the verify sees only
# what it writes.
find runs/Fig5_germination -type f \( -name '*.tsv' -o -name '*.txt' \) -delete
Rscript workflows/Fig5_germination/Fig5_germination.R
