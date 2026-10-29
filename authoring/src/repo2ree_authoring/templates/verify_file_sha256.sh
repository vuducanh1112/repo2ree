#!/usr/bin/env sh
# Verify script — checks that the experiment produced its claimed result.
# Runs from the workspace root after the run script. Exit 0 = verified.
# Nothing is injected: read whatever you check straight from the workspace.
# To check the run's stdout, have the run script write it to a file, e.g.
#   <your run command> > results/run.log
set -eu

# Claim: the output file is byte-identical to the recorded baseline.
OUTPUT_FILE='EDIT-ME results/output.csv'
EXPECTED_SHA256='EDIT-ME paste the sha256 hex digest'
[ -f "$OUTPUT_FILE" ] || { echo "output file not found: $OUTPUT_FILE" >&2; exit 1; }
actual=$(sha256sum "$OUTPUT_FILE" | cut -d' ' -f1)
[ "$actual" = "$EXPECTED_SHA256" ] || { echo "digest mismatch: got $actual" >&2; exit 1; }
