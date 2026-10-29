#!/usr/bin/env sh
set -eu

# Docker build: build the project's image and save it as the runtime artifact.
# Runs from the workspace root, where the project source lives.

# If the Dockerfile is not at the workspace root, point DOCKERFILE at it — the
# dependency analysis step lists every detected Dockerfile with its path.
DOCKERFILE="./Dockerfile"
# The build context the Dockerfile's COPY/ADD paths are relative to.
BUILD_CONTEXT="."
IMAGE_TAG="ree-runtime:latest"
# Where the saved image lands; keep this in sync with the runtime artifact
# path declared on the REE.
RUNTIME_ARTIFACT="runtime.tar"

docker build --file "$DOCKERFILE" --tag "$IMAGE_TAG" "$BUILD_CONTEXT"
docker save "$IMAGE_TAG" --output "$RUNTIME_ARTIFACT"
