#!/usr/bin/env sh
set -eu

# What script inference generates for this project (root-pip-requirements-v1):
# a venv outside the workspace, the empty requirements installed into it without
# reaching an index, and the venv packed as the runtime artifact.
REQUIREMENTS=instant_hello_world/requirements.txt
RUNTIME_ARTIFACT=instant_hello_world/runtime-venv.tar.gz
VENV_DIR=/tmp/ree-venv

python -m venv "$VENV_DIR"
"$VENV_DIR/bin/pip" install --no-cache-dir --requirement "$REQUIREMENTS"

mkdir -p "$(dirname "$RUNTIME_ARTIFACT")"
tar -czf "$RUNTIME_ARTIFACT" -C "$(dirname "$VENV_DIR")" "$(basename "$VENV_DIR")"
