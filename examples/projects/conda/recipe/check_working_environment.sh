#!/usr/bin/env sh
set -eu

fail() {
  echo "check_working_environment: $*" >&2
  exit 1
}

command -v python3 >/dev/null 2>&1 || fail "python3 is not installed"
command -v sha256sum >/dev/null 2>&1 || fail "sha256sum is not installed"
command -v tar >/dev/null 2>&1 || fail "tar is not installed"
python3 -c 'import urllib.request; urllib.request.urlopen("https://github.com", timeout=20)' 2>/dev/null ||
  fail "github.com, where micromamba comes from, is not reachable"

echo "working environment: $(uname -srm)"
