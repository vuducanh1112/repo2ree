#!/usr/bin/env sh
set -eu

IMAGE=ree-p-hacking-replication:experiment-environment
EXPERIMENT_ENVIRONMENT_ARTIFACT=.repo2ree/artifacts/experiment-environment.tar

# Load the archive unless the image its name gives is the one it holds: a name alone may give an older build.
WANTED=$(tar -xOf "$EXPERIMENT_ENVIRONMENT_ARTIFACT" manifest.json 2>/dev/null \
  | sed -n 's/.*"Config": *"\([^"]*\)".*/\1/p' | sed 's#.*/##; s/[.]json$//')
LOADED=$(docker image inspect --format '{{.Id}}' "$IMAGE" 2>/dev/null | sed 's/^sha256://')
if [ -z "$WANTED" ] || [ "$WANTED" != "$LOADED" ]; then
  docker load --input "$EXPERIMENT_ENVIRONMENT_ARTIFACT"
fi

# The workspace as the replication package root, written as this machine's user, with no network: the
# analysis reads only what the package ships and what the image holds. OpenBLAS runs one kernel on every
# x86_64 CPU, on one thread: left to choose by itself it takes a virtual CPU for an Opteron and dies on an
# instruction the CPU lacks, and its choice and its threads both move the last digits of a result. OpenMP
# runs on one thread too: fixest demeans on half the cores, the order of its sums differs run to run, and
# one of the caliper probits then never converges.
exec docker run --rm --network none \
  --user "$(id -u):$(id -g)" --env HOME=/tmp \
  --env OPENBLAS_CORETYPE=Nehalem --env OPENBLAS_NUM_THREADS=1 --env OMP_NUM_THREADS=1 \
  --volume "$PWD:/replication" --workdir /replication \
  "$IMAGE" "$@"
