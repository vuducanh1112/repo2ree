#!/usr/bin/env sh
set -eu

# Restore the packed venv where the build made it (a venv bakes absolute paths)
# and prove its interpreter starts.
RUNTIME_ARTIFACT=instant_hello_world/runtime-venv.tar.gz
# Where the build made it: the archive's top directory, under /tmp.
VENV_DIR="/tmp/$(tar -tzf "$RUNTIME_ARTIFACT" | head -n 1 | cut -d/ -f1)"

# Always fresh: on a machine other REEs share, what is there may be another's.
rm -rf "$VENV_DIR"
mkdir -p "$(dirname "$VENV_DIR")"
tar -xzf "$RUNTIME_ARTIFACT" -C "$(dirname "$VENV_DIR")"

"$VENV_DIR/bin/python" -c "import hashlib; print('activation ok')"
