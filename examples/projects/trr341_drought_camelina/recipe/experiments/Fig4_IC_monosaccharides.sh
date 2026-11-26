#!/usr/bin/env sh
set -eu

# The Fig4_IC_monosaccharides workflow alone, as its workflow.cwl runs it. Its tables go first, so the verify
# sees only what it writes.
find runs/Fig4_IC_monosaccharides -type f \( -name '*.tsv' -o -name '*.txt' \) -delete
Rscript workflows/Fig4_IC_monosaccharides/Fig4_IC_monosaccharides.R
