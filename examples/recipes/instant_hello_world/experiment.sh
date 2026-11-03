#!/usr/bin/env sh
set -eu

# Run the project in the restored venv. Its stdout is the experiment's result,
# kept as a file so the verify script and a reviewer's rerun can read it.
RUNTIME_ARTIFACT=instant_hello_world/runtime-venv.tar.gz
# Where the build made it: the archive's top directory, under /tmp.
VENV_DIR="/tmp/$(tar -tzf "$RUNTIME_ARTIFACT" | head -n 1 | cut -d/ -f1)"
RESULT=result.txt

# Always fresh: on a machine other REEs share, what is there may be another's.
rm -rf "$VENV_DIR"
mkdir -p "$(dirname "$VENV_DIR")"
tar -xzf "$RUNTIME_ARTIFACT" -C "$(dirname "$VENV_DIR")"

"$VENV_DIR/bin/python" instant_hello_world/main.py > "$RESULT"
cat "$RESULT"
