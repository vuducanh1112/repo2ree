#!/usr/bin/env sh
set -eu

# Build the project's image on the machine's Docker daemon and save it as the
# runtime artifact. The image is built FROM scratch: its root filesystem is the
# machine's static busybox, added to a copy of the project outside the
# workspace, so nothing is pulled or downloaded and the source stays as it was.
PROJECT=source
IMAGE=instant-docker-hello:latest
RUNTIME_ARTIFACT=source/runtime-image.tar

CONTEXT=$(mktemp -d)
trap 'rm -rf "$CONTEXT"' EXIT
cp -R "$PROJECT"/. "$CONTEXT"
mkdir -p "$CONTEXT/rootfs/bin"
cp -L "$(command -v busybox)" "$CONTEXT/rootfs/bin/busybox"

docker build -t "$IMAGE" "$CONTEXT"
docker save "$IMAGE" -o "$RUNTIME_ARTIFACT"
