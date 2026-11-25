#!/usr/bin/env sh
set -eu

# The dev container exactly as a developer builds it: docker-compose.dev.yml's dev service, from
# docker/dev/Dockerfile (Debian and Nix by digest, the dev shell warmed from flake.lock). The project
# name fixes the image's name, so the activation finds it again after loading the artifact.
COMPOSE_PROJECT_NAME=ree-repo2ree-dev
export COMPOSE_PROJECT_NAME
COMPOSE_FILE=docker-compose.dev.yml
EXPERIMENT_ENVIRONMENT_ARTIFACT=.repo2ree/artifacts/dev-environment.tar

IMAGE=$(docker compose -f "$COMPOSE_FILE" config --images dev)

docker compose -f "$COMPOSE_FILE" build dev

mkdir -p "$(dirname "$EXPERIMENT_ENVIRONMENT_ARTIFACT")"
docker save "$IMAGE" --output "$EXPERIMENT_ENVIRONMENT_ARTIFACT"
