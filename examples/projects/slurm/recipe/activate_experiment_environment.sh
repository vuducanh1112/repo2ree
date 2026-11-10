#!/usr/bin/env sh
set -eu

if [ -z "${SLURM_JOB_ID:-}" ]; then
  exec srun --nodes=1 --ntasks=1 --time=5 sh "$0" "$@"
fi

EXPERIMENT_ENVIRONMENT_ARTIFACT=source/runtime-venv.tar.gz
VENV_DIR="/tmp/$(tar -tzf "$EXPERIMENT_ENVIRONMENT_ARTIFACT" | head -n 1 | cut -d/ -f1)"

rm -rf "$VENV_DIR"
tar -xzf "$EXPERIMENT_ENVIRONMENT_ARTIFACT" -C "$(dirname "$VENV_DIR")"
PATH="$VENV_DIR/bin:$PATH"
export PATH
exec "$@"
