#!/usr/bin/env sh
set -eu

IMAGE=ree-heat-suicide-projection:experiment-environment
EXPERIMENT_ENVIRONMENT_ARTIFACT=.repo2ree/artifacts/experiment-environment.tar

# Load the archive unless the image its name gives is the one it holds: a name alone may give an older build.
WANTED=$(tar -xOf "$EXPERIMENT_ENVIRONMENT_ARTIFACT" manifest.json 2>/dev/null \
  | sed -n 's/.*"Config": *"\([^"]*\)".*/\1/p' | sed 's#.*/##; s/[.]json$//')
LOADED=$(docker image inspect --format '{{.Id}}' "$IMAGE" 2>/dev/null | sed 's/^sha256://')
if [ -z "$WANTED" ] || [ "$WANTED" != "$LOADED" ]; then
  docker load --input "$EXPERIMENT_ENVIRONMENT_ARTIFACT"
fi

# The capsule as Code Ocean lays it out: its code at /code, its data at /data, which the scripts read from and
# write their stages' results to, and /results for its figures. As this machine's user, with no network.
# OpenBLAS runs one kernel on every x86_64 CPU, on one thread: left to choose by itself it takes a virtual CPU
# for one it is not, and its choice and its threads both move the last digits of a result.
mkdir -p results
exec docker run --rm --network none \
  --user "$(id -u):$(id -g)" --env HOME=/tmp \
  --env OPENBLAS_CORETYPE=Nehalem --env OPENBLAS_NUM_THREADS=1 --env OMP_NUM_THREADS=1 \
  --volume "$PWD:/capsule" --volume "$PWD/code:/code" --volume "$PWD/data:/data" --volume "$PWD/results:/results" \
  --workdir /capsule \
  "$IMAGE" "$@"
