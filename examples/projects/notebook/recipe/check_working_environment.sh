#!/usr/bin/env sh
set -eu

fail() {
  echo "check_working_environment: $*" >&2
  exit 1
}

command -v python3 >/dev/null 2>&1 || fail "python3 is not installed"
python3 -c 'import sys; sys.exit(sys.version_info < (3, 11))' || fail "python3 is older than 3.11"
python3 -c 'import ensurepip, venv' 2>/dev/null || fail "python3 cannot create a venv with pip"
command -v tar >/dev/null 2>&1 || fail "tar is not installed"

echo "working environment: $(uname -srm)"
