#!/usr/bin/env sh
set -eu

EXPERIMENT_ENVIRONMENT_ARTIFACT="runtime-venv.tar.gz"
VENV_DIR="/tmp/ree-venv"

rm -rf "$VENV_DIR"
tar -xzf "$EXPERIMENT_ENVIRONMENT_ARTIFACT" -C "$(dirname "$VENV_DIR")"
PATH="$VENV_DIR/bin:$PATH"
export PATH
exec "$@"
