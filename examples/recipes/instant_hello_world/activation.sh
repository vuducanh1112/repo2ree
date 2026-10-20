#!/usr/bin/env sh
set -eu

# Restore the packed venv where the build made it (a venv bakes absolute paths)
# and prove its interpreter starts.
RUNTIME_ARTIFACT=instant_hello_world/runtime-venv.tar.gz
VENV_DIR=/tmp/ree-venv

if [ ! -x "$VENV_DIR/bin/python" ]; then
  mkdir -p "$(dirname "$VENV_DIR")"
  tar -xzf "$RUNTIME_ARTIFACT" -C "$(dirname "$VENV_DIR")"
fi

"$VENV_DIR/bin/python" -c "import hashlib; print('activation ok')"
