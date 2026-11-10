#!/usr/bin/env sh
set -eu

IMAGE=pandas-hello:latest
EXPERIMENT_ENVIRONMENT_ARTIFACT=source/runtime.tar

docker image inspect "$IMAGE" >/dev/null 2>&1 || docker load -i "$EXPERIMENT_ENVIRONMENT_ARTIFACT"
exec docker run --rm -v "$PWD:$PWD" -w "$PWD" --entrypoint "" "$IMAGE" "$@"
