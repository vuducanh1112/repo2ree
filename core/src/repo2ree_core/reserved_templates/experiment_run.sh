#!/usr/bin/env sh
set -eu

# This script fully defines how this experiment executes — it owns entering the
# runtime. Materialize the stdout you want to verify to a workspace file, so
# the verify script can read it back. For a Docker runtime, for example:
#
# docker run --rm -v "$(pwd):/workspace" -w /workspace my-runtime:latest \
#   python main.py | tee results/run.log
