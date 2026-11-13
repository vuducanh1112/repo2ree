#!/usr/bin/env sh
set -eu

exec apptainer exec source/runtime.sif "$@"
