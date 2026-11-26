#!/usr/bin/env sh
set -eu

# The TabS2_stem_count_ANCOVA workflow alone, as its workflow.cwl runs it. Its tables go first, so the verify
# sees only what it writes.
find runs/TabS2_stem_count_ANCOVA -type f \( -name '*.tsv' -o -name '*.txt' \) -delete
Rscript workflows/TabS2_stem_count_ANCOVA/TabS2_stem_count_ANCOVA.R
