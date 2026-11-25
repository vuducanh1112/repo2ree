#!/usr/bin/env sh
set -eu

fail() {
  echo "check_working_environment: $*" >&2
  exit 1
}

# The image the dev container is built from, pinned in docker/dev/Dockerfile: the build pulls it anyway.
PROBE_IMAGE=debian:trixie-slim@sha256:89c1ea91e897f0fe0a3731595330bc45b8bdef4047464a07116f891a94054b31
# A cold build holds the dev image's layers, about 8.5 GB, and saves them once more as the
# experiment environment; a rebuild on the same daemon reuses the layers.
NEEDED_KB=$((20 * 1024 * 1024))

docker info >/dev/null 2>&1 || fail "no Docker daemon is reachable"
docker compose version >/dev/null 2>&1 || fail "docker compose is not installed"

# The compose file mounts the workspace into the dev container: the daemon must see this machine's paths,
# which a daemon reached through a forwarded socket (Docker outside of Docker) does not.
PROBE=$(mktemp -d "$PWD/.mount-probe.XXXXXX")
trap 'rm -rf "$PROBE"' EXIT
echo seen > "$PROBE/probe"
[ "$(docker run --rm -v "$PROBE:/probe:ro" "$PROBE_IMAGE" cat /probe/probe 2>/dev/null)" = seen ] \
  || fail "the Docker daemon does not see $PWD: a bind mount from here comes up empty"

FREE_KB=$(df -Pk . | awk 'NR == 2 { print $4 }')
[ "$FREE_KB" -ge "$NEEDED_KB" ] || fail "needs 20 GB free here, has $((FREE_KB / 1024 / 1024)) GB"

echo "working environment: $(uname -srm), $(docker compose version --short) compose, $((FREE_KB / 1024 / 1024)) GB free"
