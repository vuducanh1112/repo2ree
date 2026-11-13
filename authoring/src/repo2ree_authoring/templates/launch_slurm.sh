#!/usr/bin/env sh
set -eu

# Runs each of the REE's scripts as a Slurm job step and waits for it: the workbench and run.sh call
# `sh launch.sh <command>` for every script. Set what the experiment needs here; a cluster's own options
# (partition, account, QOS) belong to whoever runs it, who adds them through REE_LAUNCH_OPTIONS.
CPUS=1
TIME_LIMIT=00:30:00
# Leave empty for the cluster's default memory, and for no GPUs.
MEMORY=
GPUS=

# One task on one node: the command runs once. REE_LAUNCH_OPTIONS comes last, so a reproducer's options win.
# shellcheck disable=SC2086
exec srun --nodes=1 --ntasks=1 --cpus-per-task="$CPUS" --time="$TIME_LIMIT" \
  ${MEMORY:+--mem="$MEMORY"} ${GPUS:+--gpus="$GPUS"} ${REE_LAUNCH_OPTIONS:-} "$@"
