#!/usr/bin/env sh
set -eu

docker build -t java-hello:latest source
docker save java-hello:latest -o source/runtime.tar
