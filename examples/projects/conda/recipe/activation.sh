#!/usr/bin/env sh
set -eu

RUNTIME_ARTIFACT=source/runtime-conda.tar.gz
RUNTIME_DIR=/tmp/ree-conda-runtime

rm -rf "$RUNTIME_DIR"
tar -xzf "$RUNTIME_ARTIFACT" -C "$(dirname "$RUNTIME_DIR")"

MAMBA_ROOT_PREFIX=$RUNTIME_DIR
export MAMBA_ROOT_PREFIX
eval "$("$RUNTIME_DIR/bin/micromamba" shell hook --shell posix)"
micromamba activate "$RUNTIME_DIR/env"

[ "$CONDA_PREFIX" = "$RUNTIME_DIR/env" ]
python -c "import numpy; print('activation ok: numpy', numpy.__version__)"
