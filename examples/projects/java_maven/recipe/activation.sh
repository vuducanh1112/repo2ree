#!/usr/bin/env sh
set -eu

if ! docker image inspect java-hello:latest >/dev/null 2>&1; then
  docker load < source/runtime.tar
fi

docker run --rm -v "$(pwd):/workspace" -w /workspace java-hello:latest java -version
