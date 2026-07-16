#!/usr/bin/env sh
# Verify script — checks that the experiment produced its claimed result.
# Runs from the workspace root after the run script. Exit 0 = verified.
# Nothing is injected: read whatever you check straight from the workspace.
# To check the run's stdout, have the run script write it to a file, e.g.
#   <your run command> | tee results/run.log
set -eu

# Claim: the run log contains the expected phrase.
# RUN_LOG is the file the run script materialized its stdout to.
RUN_LOG='EDIT-ME results/run.log'
grep -Fq 'EDIT-ME expected phrase' "$RUN_LOG"
