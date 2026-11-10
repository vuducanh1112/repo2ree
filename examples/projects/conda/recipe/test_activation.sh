#!/usr/bin/env sh
set -eu

[ "$CONDA_PREFIX" = /tmp/ree-conda-runtime/env ]
python -c "import numpy; print('activation ok: numpy', numpy.__version__)"
