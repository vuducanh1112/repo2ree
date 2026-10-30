#!/usr/bin/env sh
set -eu

# Build the project's image on the bench's own Docker daemon and save it as the
# runtime artifact. The image is built FROM scratch: its root filesystem is the
# bench's busybox and musl loader, added to a copy of the project outside the
# workspace, so nothing is pulled or downloaded and the source stays as it was.
PROJECT=instant_docker_hello_world
IMAGE=instant-docker-hello:latest
RUNTIME_ARTIFACT=instant_docker_hello_world/runtime-image.tar

CONTEXT=$(mktemp -d)
trap 'rm -rf "$CONTEXT"' EXIT
cp -R "$PROJECT"/. "$CONTEXT"
mkdir -p "$CONTEXT/rootfs/bin" "$CONTEXT/rootfs/lib"
cp /bin/busybox "$CONTEXT/rootfs/bin/busybox"
cp /lib/ld-musl-*.so.1 "$CONTEXT/rootfs/lib/"

docker build -t "$IMAGE" "$CONTEXT"
docker save "$IMAGE" -o "$RUNTIME_ARTIFACT"
