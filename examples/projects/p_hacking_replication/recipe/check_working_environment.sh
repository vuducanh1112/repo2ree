#!/usr/bin/env sh
set -eu

fail() {
  echo "check_working_environment: $*" >&2
  exit 1
}

# The image the experiment environment is built from: the probe pulls what the build needs anyway.
PROBE_IMAGE=rocker/r-ver:4.4.3@sha256:3dae5d2eeddf74f10e0a81fb6b7ae350295e288000304f438b844b2c1e00fe2c
# The R packages, Quarto and their layers, saved once more as the experiment environment.
NEEDED_KB=$((10 * 1024 * 1024))

# Quarto is pinned by the checksum of its x86_64 release.
[ "$(uname -m)" = x86_64 ] || fail "needs an x86_64 machine, this is $(uname -m)"
docker info >/dev/null 2>&1 || fail "no Docker daemon is reachable"
# The verify compares the regenerated tables with the ones the acquired commit holds.
command -v git >/dev/null 2>&1 || fail "git is not installed"
command -v sha256sum >/dev/null 2>&1 || fail "sha256sum is not installed"

# The activation mounts the workspace into the container: the daemon must see this machine's paths.
PROBE=$(mktemp -d "$PWD/.mount-probe.XXXXXX")
trap 'rm -rf "$PROBE"' EXIT
echo seen > "$PROBE/probe"
[ "$(docker run --rm -v "$PROBE:/probe:ro" "$PROBE_IMAGE" cat /probe/probe 2>/dev/null)" = seen ] \
  || fail "the Docker daemon does not see $PWD: a bind mount from here comes up empty"

FREE_KB=$(df -Pk . | awk 'NR == 2 { print $4 }')
[ "$FREE_KB" -ge "$NEEDED_KB" ] || fail "needs 10 GB free here, has $((FREE_KB / 1024 / 1024)) GB"

echo "working environment: $(uname -srm), Docker $(docker version --format '{{.Server.Version}}'), $((FREE_KB / 1024 / 1024)) GB free"
