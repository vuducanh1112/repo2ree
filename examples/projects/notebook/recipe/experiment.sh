#!/usr/bin/env sh
set -eu

RUNTIME_ARTIFACT=source/runtime-venv.tar.gz
VENV_DIR="/tmp/$(tar -tzf "$RUNTIME_ARTIFACT" | head -n 1 | cut -d/ -f1)"
RESULT=result.txt

rm -rf "$VENV_DIR"
tar -xzf "$RUNTIME_ARTIFACT" -C "$(dirname "$VENV_DIR")"

# The kernel runs in the notebook's folder, so what the notebook writes lands beside it.
"$VENV_DIR/bin/jupyter" execute --output=executed source/decay.ipynb
mv source/executed.ipynb source/figure.png source/figure.json source/curve.csv source/"$RESULT" .
cat "$RESULT"
