#!/usr/bin/env sh
set -eu

RUNTIME_ARTIFACT=source/runtime-venv.tar.gz
VENV_DIR="/tmp/$(tar -tzf "$RUNTIME_ARTIFACT" | head -n 1 | cut -d/ -f1)"
RESULT=result.txt

rm -rf "$VENV_DIR"
tar -xzf "$RUNTIME_ARTIFACT" -C "$(dirname "$VENV_DIR")"

"$VENV_DIR/bin/python" source/main.py > "$RESULT"
cat "$RESULT"
