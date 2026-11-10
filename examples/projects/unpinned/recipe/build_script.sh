#!/usr/bin/env sh
set -eu

UPSTREAM=@UPSTREAM_URL@
RUNTIME_ARTIFACT=source/runtime-venv.tar.gz
VENV_DIR=/tmp/ree-venv

rm -rf "$VENV_DIR"
python -m venv "$VENV_DIR"
SITE=$("$VENV_DIR/bin/python" -c 'import sysconfig; print(sysconfig.get_path("purelib"))')
"$VENV_DIR/bin/python" -c 'import sys, urllib.request; urllib.request.urlretrieve(sys.argv[1], sys.argv[2])' \
  "$UPSTREAM/latest/labunits.py" "$SITE/labunits.py"

tar -czf "$RUNTIME_ARTIFACT" -C "$(dirname "$VENV_DIR")" "$(basename "$VENV_DIR")"
