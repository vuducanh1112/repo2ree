#!/usr/bin/env sh
set -eu

# Virtual environment build: install the project's requirements into a venv and
# pack it as the runtime artifact. Runs from the workspace root, where the project
# source lives, on the workbench's own host and its Python.

REQUIREMENTS="requirements.txt"
# Outside the workspace, and this REE's own: a venv bakes absolute paths, so it is
# restored to this same directory, and REEs side by side must not share one.
VENV_DIR="/tmp/ree-venv"
# Where the packed venv lands; keep this in sync with the runtime artifact path
# declared on the REE.
RUNTIME_ARTIFACT="runtime-venv.tar.gz"

python -m venv "$VENV_DIR"
"$VENV_DIR/bin/pip" install --no-cache-dir --requirement "$REQUIREMENTS"
tar -czf "$RUNTIME_ARTIFACT" -C "$(dirname "$VENV_DIR")" "$(basename "$VENV_DIR")"
