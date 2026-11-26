#!/usr/bin/env sh
set -eu

fail() {
  echo "check_working_environment: $*" >&2
  exit 1
}

# The image the experiment environment is built from: the probe pulls what the build needs anyway.
PROBE_IMAGE=registry.codeocean.com/codeocean/py-r@sha256:405137d58b9589fc24d9374b9a0637a57cfd6020ab707db8d8f854a40def42d3
# The capsule's base image, its R packages and their layers, saved once more as the experiment environment.
NEEDED_KB=$((16 * 1024 * 1024))

[ "$(uname -m)" = x86_64 ] || fail "needs an x86_64 machine, this is $(uname -m): the capsule's image is built for no other"
docker info >/dev/null 2>&1 || fail "no Docker daemon is reachable"
command -v sha256sum >/dev/null 2>&1 || fail "sha256sum is not installed"

# The activation mounts the workspace into the container: the daemon must see this machine's paths.
PROBE=$(mktemp -d "$PWD/.mount-probe.XXXXXX")
trap 'rm -rf "$PROBE"' EXIT
echo seen > "$PROBE/probe"
[ "$(docker run --rm -v "$PROBE:/probe:ro" "$PROBE_IMAGE" cat /probe/probe 2>/dev/null)" = seen ] \
  || fail "the Docker daemon does not see $PWD: a bind mount from here comes up empty"

FREE_KB=$(df -Pk . | awk 'NR == 2 { print $4 }')
[ "$FREE_KB" -ge "$NEEDED_KB" ] || fail "needs 16 GB free here, has $((FREE_KB / 1024 / 1024)) GB"

echo "working environment: $(uname -srm), Docker $(docker version --format '{{.Server.Version}}'), $((FREE_KB / 1024 / 1024)) GB free"
