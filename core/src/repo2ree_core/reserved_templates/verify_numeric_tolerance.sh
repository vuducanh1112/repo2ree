#!/usr/bin/env sh
# Verify script — checks that the experiment produced its claimed result.
# Runs from the workspace root after the run script. Exit 0 = verified.
# Nothing is injected: read whatever you check straight from the workspace.
# To check the run's stdout, have the run script write it to a file, e.g.
#   <your run command> > results/run.log
set -eu

# Claim: the reported metric equals EXPECTED within ± EPSILON.
# EXTRACT_PATTERN pulls the number out of the run log (first match wins).
RUN_LOG='EDIT-ME results/run.log'
EXPECTED='EDIT-ME 0.9542'
EPSILON='EDIT-ME 0.001'
EXTRACT_PATTERN='[0-9]+\.[0-9]+'
actual=$(grep -Eo "$EXTRACT_PATTERN" "$RUN_LOG" | head -n 1)
[ -n "$actual" ] || { echo "no number matching the extract pattern in $RUN_LOG" >&2; exit 1; }
awk -v a="$actual" -v e="$EXPECTED" -v eps="$EPSILON" \
  'BEGIN { d = a - e; if (d < 0) d = -d; exit !(d <= eps) }'
