#!/usr/bin/env sh
set -eu

# Docker activation: prove the built runtime is inhabitable by loading the
# saved image and running a command inside it. Runs from the workspace root.

# Keep these in sync with the build script's variables.
RUNTIME_ARTIFACT="runtime.tar"
IMAGE_TAG="ree-runtime:latest"

# Loading from the saved artifact — not the locally built image — proves the
# artifact itself is self-contained.
docker load --input "$RUNTIME_ARTIFACT"

# Replace the trailing command with one that shows the runtime works.
docker run --rm -v "$(pwd):/workspace" -w /workspace "$IMAGE_TAG" \
  python main.py
