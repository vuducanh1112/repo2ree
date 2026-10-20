#!/usr/bin/env sh
set -eu

# Run the project in the restored venv. Its stdout is the experiment's result,
# kept as a file so the verify script and a reviewer's rerun can read it.
RUNTIME_ARTIFACT=instant_hello_world/runtime-venv.tar.gz
VENV_DIR=/tmp/ree-venv
RESULT=result.txt

if [ ! -x "$VENV_DIR/bin/python" ]; then
  mkdir -p "$(dirname "$VENV_DIR")"
  tar -xzf "$RUNTIME_ARTIFACT" -C "$(dirname "$VENV_DIR")"
fi

"$VENV_DIR/bin/python" instant_hello_world/main.py > "$RESULT"
cat "$RESULT"
