#!/usr/bin/env sh
set -eu

fail() {
  echo "check_working_environment: $*" >&2
  exit 1
}

docker info >/dev/null 2>&1 || fail "no Docker daemon is reachable"

echo "working environment: $(uname -srm)"
