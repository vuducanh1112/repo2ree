#!/usr/bin/env sh
set -eu

# The Manuscript_figures workflow alone, as its workflow.cwl runs it, on the models and tables of every other
# run as the ARC holds them: the authors' own, not this REE's. Its tables go first, so the verify sees only what
# it writes.
find runs/Manuscript_figures -type f \( -name '*.tsv' -o -name '*.txt' \) -delete
Rscript workflows/Manuscript_figures/Manuscript_figures.R
