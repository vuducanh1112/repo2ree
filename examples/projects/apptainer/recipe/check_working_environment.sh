#!/usr/bin/env sh
set -eu

fail() {
  echo "check_working_environment: $*" >&2
  exit 1
}

command -v srun >/dev/null 2>&1 || fail "srun is not installed"
sinfo >/dev/null 2>&1 || fail "sinfo gets no answer from Slurm"
command -v apptainer >/dev/null 2>&1 || fail "apptainer is not installed"

echo "working environment: $(uname -srm)"
