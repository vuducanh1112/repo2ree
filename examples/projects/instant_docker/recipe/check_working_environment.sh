#!/usr/bin/env sh
set -eu

fail() {
  echo "check_working_environment: $*" >&2
  exit 1
}

docker info >/dev/null 2>&1 || fail "no Docker daemon is reachable"
command -v busybox >/dev/null 2>&1 || fail "busybox, the image's root filesystem, is not installed"
! ldd "$(command -v busybox)" >/dev/null 2>&1 || fail "busybox is not statically linked"

echo "working environment: $(uname -srm)"
