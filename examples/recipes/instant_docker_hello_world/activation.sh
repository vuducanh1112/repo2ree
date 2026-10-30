#!/usr/bin/env sh
set -eu

# Load the saved image unless the daemon already has it, and prove a container
# from it starts.
IMAGE=instant-docker-hello:latest
RUNTIME_ARTIFACT=instant_docker_hello_world/runtime-image.tar

docker image inspect "$IMAGE" >/dev/null 2>&1 || docker load -i "$RUNTIME_ARTIFACT"
docker run --rm --entrypoint /bin/sh "$IMAGE" -c 'echo activation ok'
