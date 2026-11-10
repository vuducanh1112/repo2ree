#!/usr/bin/env sh
set -eu

RELEASE=2.10.0-0
RUNTIME_ARTIFACT=source/runtime-conda.tar.gz
RUNTIME_DIR=/tmp/ree-conda-runtime

case "$(uname -m)" in
  x86_64) PLATFORM=linux-64 DIGEST=701f39c06f8e6a670a0e186c8479b9e5c0502a2f0cda6cef65d83bdd2875e8bd ;;
  aarch64) PLATFORM=linux-aarch64 DIGEST=3bb56786e21b9b24024f599fe9185b4a59dc3f9f59937a42311ee583adbbb23c ;;
  *) echo "no micromamba release for $(uname -m)" >&2; exit 1 ;;
esac

rm -rf "$RUNTIME_DIR"
mkdir -p "$RUNTIME_DIR/bin"
python3 -c 'import sys, urllib.request; urllib.request.urlretrieve(sys.argv[1], sys.argv[2])' \
  "https://github.com/mamba-org/micromamba-releases/releases/download/$RELEASE/micromamba-$PLATFORM" \
  "$RUNTIME_DIR/bin/micromamba"
echo "$DIGEST  $RUNTIME_DIR/bin/micromamba" | sha256sum -c -
chmod +x "$RUNTIME_DIR/bin/micromamba"

MAMBA_ROOT_PREFIX=$(mktemp -d)
export MAMBA_ROOT_PREFIX
trap 'rm -rf "$MAMBA_ROOT_PREFIX"' EXIT
"$RUNTIME_DIR/bin/micromamba" create --yes --prefix "$RUNTIME_DIR/env" --file source/environment.yml

tar -czf "$RUNTIME_ARTIFACT" -C "$(dirname "$RUNTIME_DIR")" "$(basename "$RUNTIME_DIR")"
