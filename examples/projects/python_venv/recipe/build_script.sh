#!/usr/bin/env sh
set -eu

RUNTIME_ARTIFACT=source/runtime-venv.tar.gz
VENV_DIR=/tmp/ree-venv

python -m venv "$VENV_DIR"
"$VENV_DIR/bin/pip" install --no-cache-dir --requirement source/requirements.txt
tar -czf "$RUNTIME_ARTIFACT" -C "$(dirname "$VENV_DIR")" "$(basename "$VENV_DIR")"
