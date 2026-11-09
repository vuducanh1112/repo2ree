#!/usr/bin/env sh
set -eu

# Virtual environment activation: prove the built runtime is inhabitable by
# restoring the packed venv and running a command with it. Runs from the workspace root.

# Keep these in sync with the build script's variables.
RUNTIME_ARTIFACT="runtime-venv.tar.gz"
VENV_DIR="/tmp/ree-venv"

# Restoring from the packed artifact, not the venv the build left behind, proves
# the artifact itself is enough.
rm -rf "$VENV_DIR"
tar -xzf "$RUNTIME_ARTIFACT" -C "$(dirname "$VENV_DIR")"

# Replace the trailing command with one that shows the runtime works.
"$VENV_DIR/bin/python" main.py
