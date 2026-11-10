#!/usr/bin/env sh
set -eu

docker build -t pandas-hello:latest source
docker save pandas-hello:latest -o source/runtime.tar
