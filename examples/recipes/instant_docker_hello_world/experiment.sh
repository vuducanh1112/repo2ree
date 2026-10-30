#!/usr/bin/env sh
set -eu

# Run the project's container. Its stdout is the experiment's result, kept as a
# file so the verify script and a reviewer's rerun can read it.
IMAGE=instant-docker-hello:latest
RUNTIME_ARTIFACT=instant_docker_hello_world/runtime-image.tar
RESULT=result.txt

docker image inspect "$IMAGE" >/dev/null 2>&1 || docker load -i "$RUNTIME_ARTIFACT"
docker run --rm "$IMAGE" > "$RESULT"
cat "$RESULT"
