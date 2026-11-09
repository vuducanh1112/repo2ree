#!/usr/bin/env sh
set -eu

# Virtual environment experiment run: restore the packed venv and run the experiment
# with it. Runs from the workspace root. Materialize the stdout you want to verify
# to a workspace file, so the verify script can read it back.

# Keep these in sync with the build script's variables.
RUNTIME_ARTIFACT="runtime-venv.tar.gz"
VENV_DIR="/tmp/ree-venv"
# The workspace file the verify script reads the run's stdout from.
RUN_LOG="results/run.log"

# Restoring from the packed artifact, not the venv the build left behind, proves
# the artifact itself is enough.
rm -rf "$VENV_DIR"
tar -xzf "$RUNTIME_ARTIFACT" -C "$(dirname "$VENV_DIR")"

mkdir -p "$(dirname "$RUN_LOG")"
# Replace the trailing command with the experiment's entry point. Stdout is
# materialized via a redirect, not `| tee`: a pipeline would report tee's
# exit status and mask a failing run.
"$VENV_DIR/bin/python" main.py > "$RUN_LOG"
cat "$RUN_LOG"
