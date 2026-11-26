#!/usr/bin/env sh
set -eu

IMAGE=ree-trr341-drought-camelina:experiment-environment
EXPERIMENT_ENVIRONMENT_ARTIFACT=.repo2ree/artifacts/experiment-environment.tar

# Load the archive unless the image its name gives is the one it holds: a name alone may give an older build.
WANTED=$(tar -xOf "$EXPERIMENT_ENVIRONMENT_ARTIFACT" manifest.json 2>/dev/null \
  | sed -n 's/.*"Config": *"\([^"]*\)".*/\1/p' | sed 's#.*/##; s/[.]json$//')
LOADED=$(docker image inspect --format '{{.Id}}' "$IMAGE" 2>/dev/null | sed 's/^sha256://')
if [ -z "$WANTED" ] || [ "$WANTED" != "$LOADED" ]; then
  docker load --input "$EXPERIMENT_ENVIRONMENT_ARTIFACT"
fi

# The workspace as the ARC root, which the workflows read their inputs below and write their runs to, as this
# machine's user, with no network. OpenMP on one thread: glmmTMB's sums then come in one order, run to run.
exec docker run --rm --network none \
  --user "$(id -u):$(id -g)" --env HOME=/tmp \
  --env OMP_NUM_THREADS=1 \
  --env ARC_ROOT=/arc \
  --volume "$PWD:/arc" --workdir /arc \
  "$IMAGE" "$@"
