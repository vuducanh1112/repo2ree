#!/usr/bin/env sh
set -eu

# The Fig1_plant_area_gsw_tleaf workflow alone, as its workflow.cwl runs it. Its tables go first, so the verify
# sees only what it writes.
find runs/Fig1_plant_area_gsw_tleaf -type f \( -name '*.tsv' -o -name '*.txt' \) -delete
Rscript workflows/Fig1_plant_area_gsw_tleaf/Fig1_plant_area_gsw_tleaf.R
