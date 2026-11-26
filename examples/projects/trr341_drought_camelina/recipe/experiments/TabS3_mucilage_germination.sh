#!/usr/bin/env sh
set -eu

# The TabS3_mucilage_germination workflow alone, as its workflow.cwl runs it, on Fig4's biological replicate
# means as the ARC holds them: the authors' own, not this REE's. Its tables go first, so the verify sees only
# what it writes.
find runs/TabS3_mucilage_germination -type f \( -name '*.tsv' -o -name '*.txt' \) -delete
Rscript workflows/TabS3_mucilage_germination/TabS3_mucilage_germination.R
