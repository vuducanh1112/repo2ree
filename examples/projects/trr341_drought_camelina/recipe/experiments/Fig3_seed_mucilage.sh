#!/usr/bin/env sh
set -eu

# The Fig3_seed_mucilage workflow alone, as its workflow.cwl runs it. Its tables go first, so the verify sees
# only what it writes.
find runs/Fig3_seed_mucilage -type f \( -name '*.tsv' -o -name '*.txt' \) -delete
Rscript workflows/Fig3_seed_mucilage/Fig3_seed_mucilage.R
