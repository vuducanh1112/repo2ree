#!/usr/bin/env sh
# Verify script — checks that the experiment produced its claimed result.
# Runs from the workspace root after the run script. Exit 0 = verified.
# Nothing is injected: read whatever you check straight from the workspace.
# To check the run's stdout, have the run script write it to a file, e.g.
#   <your run command> > results/run.log
set -eu

# Claim: the run log matches the expected pattern.
RUN_LOG='EDIT-ME results/run.log'
PATTERN='EDIT-ME: accuracy: 0\.9[0-9]+'
grep -Eq "$PATTERN" "$RUN_LOG"
