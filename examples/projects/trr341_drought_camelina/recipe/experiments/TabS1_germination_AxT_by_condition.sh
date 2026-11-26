#!/usr/bin/env sh
set -eu

# The TabS1_germination_AxT_by_condition workflow alone, as its workflow.cwl runs it. Its tables go first, so
# the verify sees only what it writes.
find runs/TabS1_germination_AxT_by_condition -type f \( -name '*.tsv' -o -name '*.txt' \) -delete
Rscript workflows/TabS1_germination_AxT_by_condition/TabS1_germination_AxT_by_condition.R
