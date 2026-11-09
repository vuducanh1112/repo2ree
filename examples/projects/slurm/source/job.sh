#!/usr/bin/env sh
set -eu

# One Slurm task: restore the packed venv on the node the job landed on, note the
# job, and run Python with this script's arguments.
RUNTIME_ARTIFACT=source/runtime-venv.tar.gz
VENV_DIR="/tmp/$(tar -tzf "$RUNTIME_ARTIFACT" | head -n 1 | cut -d/ -f1)"

rm -rf "$VENV_DIR"
tar -xzf "$RUNTIME_ARTIFACT" -C "$(dirname "$VENV_DIR")"

echo "$SLURM_JOB_ID" > slurm-job.txt
exec "$VENV_DIR/bin/python" "$@"
