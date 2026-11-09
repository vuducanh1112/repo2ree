#!/usr/bin/env sh
set -eu

if ! docker image inspect pandas-hello:latest >/dev/null 2>&1; then
  docker load < source/runtime.tar
fi

docker run --rm -v "$(pwd):/workspace" -w /workspace pandas-hello:latest python -c "import pandas; print('activation ok')"
