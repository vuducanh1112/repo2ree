#!/usr/bin/env sh
set -eu

# Build the SIF from the project's definition file. Its root filesystem is this
# machine's own Python and system directories, so nothing is pulled or downloaded.
apptainer build --force source/runtime.sif source/runtime.def
