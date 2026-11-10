#!/usr/bin/env sh
set -eu

EXPERIMENT_ENVIRONMENT_ARTIFACT=source/runtime-conda.tar.gz
RUNTIME_DIR=/tmp/ree-conda-runtime

rm -rf "$RUNTIME_DIR"
tar -xzf "$EXPERIMENT_ENVIRONMENT_ARTIFACT" -C "$(dirname "$RUNTIME_DIR")"
MAMBA_ROOT_PREFIX=$RUNTIME_DIR
export MAMBA_ROOT_PREFIX
eval "$("$RUNTIME_DIR/bin/micromamba" shell hook --shell posix)"
micromamba activate "$RUNTIME_DIR/env"
exec "$@"
