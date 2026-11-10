#!/usr/bin/env sh
set -eu

RUNTIME_ARTIFACT=source/runtime-venv.tar.gz
VENV_DIR="/tmp/$(tar -tzf "$RUNTIME_ARTIFACT" | head -n 1 | cut -d/ -f1)"

rm -rf "$VENV_DIR"
tar -xzf "$RUNTIME_ARTIFACT" -C "$(dirname "$VENV_DIR")"

"$VENV_DIR/bin/jupyter" kernelspec list | grep -q '^ *python3 '
"$VENV_DIR/bin/python" -c "import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot, nbclient, numpy; print('activation ok')"
