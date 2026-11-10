#!/usr/bin/env sh
set -eu

EXPERIMENT_ENVIRONMENT_ARTIFACT="runtime.tar"
IMAGE_TAG="ree-runtime:latest"

docker image inspect "$IMAGE_TAG" >/dev/null 2>&1 || docker load --input "$EXPERIMENT_ENVIRONMENT_ARTIFACT"
exec docker run --rm -v "$PWD:$PWD" -w "$PWD" --entrypoint "" "$IMAGE_TAG" "$@"
