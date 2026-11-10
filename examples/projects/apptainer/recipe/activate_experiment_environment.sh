#!/usr/bin/env sh
set -eu

exec srun --nodes=1 --ntasks=1 --time=5 apptainer exec source/runtime.sif "$@"
