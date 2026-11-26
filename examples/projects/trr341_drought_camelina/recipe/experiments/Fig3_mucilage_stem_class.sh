#!/usr/bin/env sh
set -eu

# The Fig3_mucilage_stem_class workflow alone, as its workflow.cwl runs it. Its tables go first, so the verify
# sees only what it writes.
find runs/Fig3_mucilage_stem_class -type f \( -name '*.tsv' -o -name '*.txt' \) -delete
Rscript workflows/Fig3_mucilage_stem_class/Fig3_mucilage_stem_class.R
