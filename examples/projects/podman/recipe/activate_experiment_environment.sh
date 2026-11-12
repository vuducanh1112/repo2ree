#!/usr/bin/env sh
set -eu

IMAGE=localhost/podman-hello:latest
EXPERIMENT_ENVIRONMENT_ARTIFACT=source/runtime.tar

podman image exists "$IMAGE" || podman load --input "$EXPERIMENT_ENVIRONMENT_ARTIFACT"
exec podman run --rm -v "$PWD:$PWD" -w "$PWD" "$IMAGE" "$@"
