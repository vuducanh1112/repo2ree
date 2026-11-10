#!/usr/bin/env sh
set -eu

IMAGE=instant-docker-hello:latest
EXPERIMENT_ENVIRONMENT_ARTIFACT=source/runtime-image.tar

docker image inspect "$IMAGE" >/dev/null 2>&1 || docker load -i "$EXPERIMENT_ENVIRONMENT_ARTIFACT"
exec docker run --rm -v "$PWD:$PWD" -w "$PWD" --entrypoint "" "$IMAGE" "$@"
