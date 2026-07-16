#!/usr/bin/env sh
set -eu

# Docker experiment run: load the saved runtime image and run the experiment
# inside it. Runs from the workspace root. Materialize the stdout you want to
# verify to a workspace file, so the verify script can read it back.

# Keep these in sync with the build script's variables.
RUNTIME_ARTIFACT="runtime.tar"
IMAGE_TAG="ree-runtime:latest"
# The workspace file the verify script reads the run's stdout from.
RUN_LOG="results/run.log"

# Loading from the saved artifact — not the locally built image — proves the
# artifact itself is self-contained.
docker load --input "$RUNTIME_ARTIFACT"

mkdir -p "$(dirname "$RUN_LOG")"
# Replace the trailing command with the experiment's entry point. Stdout is
# materialized via a redirect, not `| tee`: a pipeline would report tee's
# exit status and mask a failing run.
docker run --rm -v "$(pwd):/workspace" -w /workspace "$IMAGE_TAG" \
  python main.py > "$RUN_LOG"
cat "$RUN_LOG"
