#!/usr/bin/env sh
set -eu

fail() {
  echo "check_working_environment: $*" >&2
  exit 1
}

podman info >/dev/null 2>&1 || fail "podman cannot run containers here"

echo "working environment: $(uname -srm)"
