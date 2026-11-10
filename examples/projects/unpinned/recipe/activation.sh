#!/usr/bin/env sh
set -eu

RUNTIME_ARTIFACT=source/runtime-venv.tar.gz
VENV_DIR=/tmp/ree-venv

rm -rf "$VENV_DIR"
tar -xzf "$RUNTIME_ARTIFACT" -C "$(dirname "$VENV_DIR")"

"$VENV_DIR/bin/python" -c "import labunits; print('activation ok')"
