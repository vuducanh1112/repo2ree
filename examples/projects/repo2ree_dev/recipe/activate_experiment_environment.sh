#!/usr/bin/env sh
set -eu

COMPOSE_PROJECT_NAME=ree-repo2ree-dev
export COMPOSE_PROJECT_NAME
COMPOSE_FILE=docker-compose.dev.yml
EXPERIMENT_ENVIRONMENT_ARTIFACT=.repo2ree/artifacts/dev-environment.tar

IMAGE=$(docker compose -f "$COMPOSE_FILE" config --images dev)

# Load the archive unless the image its name gives is the one it holds: a name alone may give an older build.
WANTED=$(tar -xOf "$EXPERIMENT_ENVIRONMENT_ARTIFACT" manifest.json 2>/dev/null \
  | sed -n 's/.*"Config": *"\([^"]*\)".*/\1/p' | sed 's#.*/##; s/[.]json$//')
LOADED=$(docker image inspect --format '{{.Id}}' "$IMAGE" 2>/dev/null | sed 's/^sha256://')
if [ -z "$WANTED" ] || [ "$WANTED" != "$LOADED" ]; then
  docker load --input "$EXPERIMENT_ENVIRONMENT_ARTIFACT"
fi

# Inside the dev container, direnv loads the dev shell and .venv as it does for a developer: the
# entrypoint takes on the workspace owner's IDs, and the activation holds only once the repo's own
# tools answer from the Nix store.
exec docker compose -f "$COMPOSE_FILE" run --rm -T dev \
  direnv exec /repo2ree sh -c '
    command -v just | grep -q "^/nix/store/" || { echo "the dev shell did not load: just is not from /nix/store" >&2; exit 1; }
    command -v uv | grep -q "^/nix/store/" || { echo "the dev shell did not load: uv is not from /nix/store" >&2; exit 1; }
    exec "$@"
  ' sh "$@"
