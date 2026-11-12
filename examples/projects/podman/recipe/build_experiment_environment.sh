#!/usr/bin/env sh
set -eu

# Build the project's Containerfile with rootless Podman and save the image as the
# experiment environment.
IMAGE=localhost/podman-hello:latest
EXPERIMENT_ENVIRONMENT_ARTIFACT=source/runtime.tar

podman build --tag "$IMAGE" --file source/Containerfile source
podman save --output "$EXPERIMENT_ENVIRONMENT_ARTIFACT" "$IMAGE"
